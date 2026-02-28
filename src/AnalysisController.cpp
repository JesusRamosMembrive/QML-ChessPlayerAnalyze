#include "AnalysisController.h"

#include <QCoreApplication>
#include <QDir>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcessEnvironment>

AnalysisController::AnalysisController(QObject *parent)
    : QObject(parent)
{
}

AnalysisController::~AnalysisController()
{
    cancelAnalysis();
}

// ── Property getters ──

bool AnalysisController::isChecking() const { return m_isChecking; }
bool AnalysisController::playerExists() const { return m_playerExists; }
int AnalysisController::gamesAvailable() const { return m_gamesAvailable; }
int AnalysisController::monthsAvailable() const { return m_monthsAvailable; }

QString AnalysisController::username() const { return m_username; }

void AnalysisController::setUsername(const QString &username)
{
    if (m_username != username) {
        m_username = username;
        emit usernameChanged();
    }
}

bool AnalysisController::isAnalyzing() const { return m_isAnalyzing; }
double AnalysisController::progress() const { return m_progress; }
QString AnalysisController::progressText() const { return m_progressText; }
QString AnalysisController::errorMessage() const { return m_errorMessage; }

double AnalysisController::suspicionScore() const { return m_suspicionScore; }
QString AnalysisController::riskLevel() const { return m_riskLevel; }
double AnalysisController::acplMean() const { return m_acplMean; }
int AnalysisController::gamesCount() const { return m_gamesCount; }
double AnalysisController::top1MatchRate() const { return m_top1MatchRate; }
double AnalysisController::blunderRate() const { return m_blunderRate; }

// ── Helpers ──

static QProcessEnvironment pythonEnv()
{
    QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
    env.insert(QStringLiteral("PYTHONIOENCODING"), QStringLiteral("utf-8"));
    env.insert(QStringLiteral("PYTHONUTF8"), QStringLiteral("1"));
    return env;
}

QString AnalysisController::findPythonPath() const
{
    return QStringLiteral("python");
}

QString AnalysisController::findCliPath() const
{
    QString appDir = QCoreApplication::applicationDirPath();
    QDir searchDir(appDir);

    for (int i = 0; i < 5; ++i) {
        QString candidate = searchDir.absoluteFilePath("python/cli.py");
        if (QFile::exists(candidate))
            return candidate;
        searchDir.cdUp();
    }
    return {};
}

// ── checkPlayer ──

void AnalysisController::checkPlayer(const QString &username)
{
    if (m_checkProcess) {
        m_checkProcess->kill();
        m_checkProcess->waitForFinished(2000);
        delete m_checkProcess;
        m_checkProcess = nullptr;
    }

    m_playerExists = false;
    m_gamesAvailable = 0;
    m_monthsAvailable = 0;
    m_errorMessage.clear();
    m_checkOutputBuffer.clear();

    setUsername(username);
    setIsChecking(true);

    QString cliPath = findCliPath();
    if (cliPath.isEmpty()) {
        setErrorMessage(QStringLiteral("Cannot find python/cli.py"));
        setIsChecking(false);
        emit errorOccurred();
        return;
    }

    m_checkProcess = new QProcess(this);
    m_checkProcess->setProcessEnvironment(pythonEnv());

    connect(m_checkProcess, &QProcess::readyReadStandardOutput,
            this, &AnalysisController::onCheckReadyRead);
    connect(m_checkProcess, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, &AnalysisController::onCheckFinished);

    QStringList args;
    args << cliPath << "check" << "--username" << username;

    m_checkProcess->start(findPythonPath(), args);

    if (!m_checkProcess->waitForStarted(5000)) {
        setErrorMessage(QStringLiteral("Failed to start Python: ") + m_checkProcess->errorString());
        setIsChecking(false);
        emit errorOccurred();
        delete m_checkProcess;
        m_checkProcess = nullptr;
    }
}

void AnalysisController::onCheckReadyRead()
{
    m_checkOutputBuffer.append(m_checkProcess->readAllStandardOutput());
}

void AnalysisController::onCheckFinished(int exitCode, QProcess::ExitStatus exitStatus)
{
    m_checkOutputBuffer.append(m_checkProcess->readAllStandardOutput());

    // Process all lines
    while (true) {
        int idx = m_checkOutputBuffer.indexOf('\n');
        if (idx < 0) {
            // Process remaining data as last line
            if (!m_checkOutputBuffer.trimmed().isEmpty()) {
                processCheckJsonLine(m_checkOutputBuffer.trimmed());
                m_checkOutputBuffer.clear();
            }
            break;
        }

        QByteArray line = m_checkOutputBuffer.left(idx).trimmed();
        m_checkOutputBuffer.remove(0, idx + 1);
        if (!line.isEmpty())
            processCheckJsonLine(line);
    }

    if ((exitStatus == QProcess::CrashExit || exitCode != 0) && m_errorMessage.isEmpty()) {
        setErrorMessage(QStringLiteral("Check failed (exit code: %1)").arg(exitCode));
        emit errorOccurred();
    }

    setIsChecking(false);

    m_checkProcess->deleteLater();
    m_checkProcess = nullptr;
}

void AnalysisController::processCheckJsonLine(const QByteArray &line)
{
    QJsonParseError parseError;
    QJsonDocument doc = QJsonDocument::fromJson(line, &parseError);
    if (parseError.error != QJsonParseError::NoError || !doc.isObject())
        return;

    QJsonObject obj = doc.object();
    QString type = obj.value("type").toString();

    if (type == "result") {
        m_playerExists = obj.value("exists").toBool();
        m_gamesAvailable = obj.value("games_available").toInt();
        m_monthsAvailable = obj.value("months").toInt();
        emit checkComplete();
    } else if (type == "error") {
        setErrorMessage(obj.value("message").toString());
        emit errorOccurred();
    }
}

// ── startAnalysis ──

void AnalysisController::startAnalysis(const QString &username, int games,
                                       int depth, int workers)
{
    if (m_isAnalyzing)
        cancelAnalysis();

    m_username = username;
    emit usernameChanged();

    m_suspicionScore = 0.0;
    m_riskLevel.clear();
    m_acplMean = 0.0;
    m_gamesCount = 0;
    m_top1MatchRate = 0.0;
    m_blunderRate = 0.0;
    m_errorMessage.clear();
    m_outputBuffer.clear();

    setProgress(0.0);
    setProgressText(QStringLiteral("Starting analysis..."));
    setIsAnalyzing(true);

    QString cliPath = findCliPath();
    if (cliPath.isEmpty()) {
        setErrorMessage(QStringLiteral("Cannot find python/cli.py"));
        setIsAnalyzing(false);
        emit errorOccurred();
        return;
    }

    m_process = new QProcess(this);
    m_process->setProcessEnvironment(pythonEnv());

    connect(m_process, &QProcess::readyReadStandardOutput,
            this, &AnalysisController::onReadyReadStandardOutput);
    connect(m_process, &QProcess::readyReadStandardError,
            this, &AnalysisController::onReadyReadStandardError);
    connect(m_process, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, &AnalysisController::onProcessFinished);

    QStringList arguments;
    arguments << cliPath
              << "analyze"
              << "--username" << username
              << "--games" << QString::number(games)
              << "--depth" << QString::number(depth)
              << "--workers" << QString::number(workers);

    m_process->start(findPythonPath(), arguments);

    if (!m_process->waitForStarted(5000)) {
        setErrorMessage(QStringLiteral("Failed to start Python: ") + m_process->errorString());
        setIsAnalyzing(false);
        emit errorOccurred();
        delete m_process;
        m_process = nullptr;
    }
}

void AnalysisController::cancelAnalysis()
{
    if (m_process) {
        m_process->kill();
        m_process->waitForFinished(3000);
        delete m_process;
        m_process = nullptr;
    }

    if (m_isAnalyzing) {
        setProgressText(QStringLiteral("Analysis cancelled"));
        setIsAnalyzing(false);
    }
}

void AnalysisController::reset()
{
    cancelAnalysis();

    m_playerExists = false;
    m_gamesAvailable = 0;
    m_monthsAvailable = 0;
    m_errorMessage.clear();
    m_suspicionScore = 0.0;
    m_riskLevel.clear();
    m_acplMean = 0.0;
    m_gamesCount = 0;
    m_top1MatchRate = 0.0;
    m_blunderRate = 0.0;

    setProgress(0.0);
    setProgressText({});
    emit checkComplete();
}

// ── Analysis process slots ──

void AnalysisController::onReadyReadStandardOutput()
{
    m_outputBuffer.append(m_process->readAllStandardOutput());

    while (true) {
        int idx = m_outputBuffer.indexOf('\n');
        if (idx < 0) break;

        QByteArray line = m_outputBuffer.left(idx).trimmed();
        m_outputBuffer.remove(0, idx + 1);

        if (!line.isEmpty())
            processJsonLine(line);
    }
}

void AnalysisController::onReadyReadStandardError()
{
    QByteArray data = m_process->readAllStandardError();
    if (!data.isEmpty())
        qWarning() << "Python stderr:" << data;
}

void AnalysisController::onProcessFinished(int exitCode, QProcess::ExitStatus exitStatus)
{
    m_outputBuffer.append(m_process->readAllStandardOutput());
    while (true) {
        int idx = m_outputBuffer.indexOf('\n');
        if (idx < 0) break;

        QByteArray line = m_outputBuffer.left(idx).trimmed();
        m_outputBuffer.remove(0, idx + 1);

        if (!line.isEmpty())
            processJsonLine(line);
    }

    if ((exitStatus == QProcess::CrashExit || exitCode != 0) && m_errorMessage.isEmpty()) {
        setErrorMessage(QStringLiteral("Analysis failed (exit code: %1)").arg(exitCode));
        emit errorOccurred();
    }

    setIsAnalyzing(false);

    m_process->deleteLater();
    m_process = nullptr;
}

void AnalysisController::processJsonLine(const QByteArray &line)
{
    QJsonParseError parseError;
    QJsonDocument doc = QJsonDocument::fromJson(line, &parseError);
    if (parseError.error != QJsonParseError::NoError || !doc.isObject())
        return;

    QJsonObject obj = doc.object();
    QString type = obj.value("type").toString();

    if (type == "status") {
        setProgressText(obj.value("message").toString());
    } else if (type == "progress") {
        int analyzed = obj.value("analyzed").toInt();
        int total = obj.value("total").toInt();
        if (total > 0)
            setProgress(static_cast<double>(analyzed) / total);
        setProgressText(obj.value("message").toString());
    } else if (type == "result") {
        m_suspicionScore = obj.value("suspicion_score").toDouble();
        m_riskLevel = obj.value("risk_level").toString();
        m_acplMean = obj.value("acpl_mean").toDouble();
        m_gamesCount = obj.value("games_count").toInt();
        m_top1MatchRate = obj.value("top1_match_rate").toDouble();
        m_blunderRate = obj.value("blunder_rate").toDouble();
        setProgress(1.0);
        setProgressText(QStringLiteral("Analysis complete"));
        emit resultReady();
    } else if (type == "error") {
        setErrorMessage(obj.value("message").toString());
        emit errorOccurred();
    }
}

// ── Private setters ──

void AnalysisController::setIsAnalyzing(bool v)
{
    if (m_isAnalyzing != v) { m_isAnalyzing = v; emit isAnalyzingChanged(); }
}

void AnalysisController::setIsChecking(bool v)
{
    if (m_isChecking != v) { m_isChecking = v; emit isCheckingChanged(); }
}

void AnalysisController::setProgress(double v)
{
    if (!qFuzzyCompare(m_progress, v)) { m_progress = v; emit progressChanged(); }
}

void AnalysisController::setProgressText(const QString &v)
{
    if (m_progressText != v) { m_progressText = v; emit progressTextChanged(); }
}

void AnalysisController::setErrorMessage(const QString &v)
{
    if (m_errorMessage != v) { m_errorMessage = v; }
}
