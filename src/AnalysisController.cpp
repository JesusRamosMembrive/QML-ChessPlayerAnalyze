#include "AnalysisController.h"

#include <QCoreApplication>
#include <QDir>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcessEnvironment>
#include <QStandardPaths>

AnalysisController::AnalysisController(QObject *parent)
    : QObject(parent)
{
}

AnalysisController::~AnalysisController()
{
    cancelAnalysis();
}

// Property getters

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
double AnalysisController::suspicionScore() const { return m_suspicionScore; }
QString AnalysisController::riskLevel() const { return m_riskLevel; }
double AnalysisController::acplMean() const { return m_acplMean; }
int AnalysisController::gamesCount() const { return m_gamesCount; }
double AnalysisController::top1MatchRate() const { return m_top1MatchRate; }
double AnalysisController::blunderRate() const { return m_blunderRate; }
QString AnalysisController::errorMessage() const { return m_errorMessage; }

// Public methods

void AnalysisController::startAnalysis(const QString &username, int games)
{
    if (m_isAnalyzing) {
        cancelAnalysis();
    }

    // Reset state
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

    // Find python path
    QString pythonPath = findPythonPath();

    // Build path to cli.py relative to the executable
    QString appDir = QCoreApplication::applicationDirPath();
    // Navigate from build dir to project root
    QDir dir(appDir);

    // Try multiple possible locations for cli.py
    QStringList searchPaths;
    searchPaths << dir.absoluteFilePath("python/cli.py");

    // Go up directories to find the project root
    QDir searchDir(appDir);
    for (int i = 0; i < 5; ++i) {
        searchPaths << searchDir.absoluteFilePath("python/cli.py");
        searchDir.cdUp();
    }

    QString cliPath;
    for (const auto &path : searchPaths) {
        if (QFile::exists(path)) {
            cliPath = path;
            break;
        }
    }

    if (cliPath.isEmpty()) {
        setErrorMessage(QStringLiteral("Cannot find python/cli.py"));
        setIsAnalyzing(false);
        emit errorOccurred();
        return;
    }

    // Launch QProcess
    m_process = new QProcess(this);

    // Force UTF-8 encoding so Python can write emojis/unicode to stdout
    QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
    env.insert(QStringLiteral("PYTHONIOENCODING"), QStringLiteral("utf-8"));
    env.insert(QStringLiteral("PYTHONUTF8"), QStringLiteral("1"));
    m_process->setProcessEnvironment(env);

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
              << "--games" << QString::number(games);

    m_process->start(pythonPath, arguments);

    if (!m_process->waitForStarted(5000)) {
        setErrorMessage(QStringLiteral("Failed to start Python process: ") + m_process->errorString());
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

// Private slots

void AnalysisController::onReadyReadStandardOutput()
{
    m_outputBuffer.append(m_process->readAllStandardOutput());

    // Process complete lines
    while (true) {
        int newlineIdx = m_outputBuffer.indexOf('\n');
        if (newlineIdx < 0) break;

        QByteArray line = m_outputBuffer.left(newlineIdx).trimmed();
        m_outputBuffer.remove(0, newlineIdx + 1);

        if (!line.isEmpty()) {
            processJsonLine(line);
        }
    }
}

void AnalysisController::onReadyReadStandardError()
{
    QByteArray stderrData = m_process->readAllStandardError();
    if (!stderrData.isEmpty()) {
        qWarning() << "Python stderr:" << stderrData;
    }
}

void AnalysisController::onProcessFinished(int exitCode, QProcess::ExitStatus exitStatus)
{
    // Process any remaining buffered output
    m_outputBuffer.append(m_process->readAllStandardOutput());
    while (true) {
        int newlineIdx = m_outputBuffer.indexOf('\n');
        if (newlineIdx < 0) break;

        QByteArray line = m_outputBuffer.left(newlineIdx).trimmed();
        m_outputBuffer.remove(0, newlineIdx + 1);

        if (!line.isEmpty()) {
            processJsonLine(line);
        }
    }

    if (exitStatus == QProcess::CrashExit || exitCode != 0) {
        if (m_errorMessage.isEmpty()) {
            setErrorMessage(QStringLiteral("Analysis process failed (exit code: %1)").arg(exitCode));
            emit errorOccurred();
        }
    }

    setIsAnalyzing(false);

    m_process->deleteLater();
    m_process = nullptr;
}

// Private methods

void AnalysisController::processJsonLine(const QByteArray &line)
{
    QJsonParseError parseError;
    QJsonDocument doc = QJsonDocument::fromJson(line, &parseError);

    if (parseError.error != QJsonParseError::NoError || !doc.isObject()) {
        return; // Skip non-JSON lines
    }

    QJsonObject obj = doc.object();
    QString type = obj.value("type").toString();

    if (type == "status") {
        setProgressText(obj.value("message").toString());

    } else if (type == "progress") {
        int analyzed = obj.value("analyzed").toInt();
        int total = obj.value("total").toInt();

        if (total > 0) {
            setProgress(static_cast<double>(analyzed) / total);
        }
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

void AnalysisController::setIsAnalyzing(bool analyzing)
{
    if (m_isAnalyzing != analyzing) {
        m_isAnalyzing = analyzing;
        emit isAnalyzingChanged();
    }
}

void AnalysisController::setProgress(double progress)
{
    if (!qFuzzyCompare(m_progress, progress)) {
        m_progress = progress;
        emit progressChanged();
    }
}

void AnalysisController::setProgressText(const QString &text)
{
    if (m_progressText != text) {
        m_progressText = text;
        emit progressTextChanged();
    }
}

void AnalysisController::setErrorMessage(const QString &message)
{
    if (m_errorMessage != message) {
        m_errorMessage = message;
    }
}

QString AnalysisController::findPythonPath() const
{
    // Check common Python locations on Windows
    QStringList candidates = {
        "python",
        "python3",
        "py",
    };

    // Check if PYTHON_PATH environment variable is set
    QString envPython = qEnvironmentVariable("PYTHON_PATH");
    if (!envPython.isEmpty()) {
        candidates.prepend(envPython);
    }

    // Just return "python" and let the system PATH resolve it
    return QStringLiteral("python");
}
