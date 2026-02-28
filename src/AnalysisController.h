#ifndef ANALYSISCONTROLLER_H
#define ANALYSISCONTROLLER_H

#include <QObject>
#include <QProcess>
#include <QQmlEngine>

class AnalysisController : public QObject
{
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(QString username READ username WRITE setUsername NOTIFY usernameChanged)
    Q_PROPERTY(bool isAnalyzing READ isAnalyzing NOTIFY isAnalyzingChanged)
    Q_PROPERTY(double progress READ progress NOTIFY progressChanged)
    Q_PROPERTY(QString progressText READ progressText NOTIFY progressTextChanged)
    Q_PROPERTY(double suspicionScore READ suspicionScore NOTIFY resultReady)
    Q_PROPERTY(QString riskLevel READ riskLevel NOTIFY resultReady)
    Q_PROPERTY(double acplMean READ acplMean NOTIFY resultReady)
    Q_PROPERTY(int gamesCount READ gamesCount NOTIFY resultReady)
    Q_PROPERTY(double top1MatchRate READ top1MatchRate NOTIFY resultReady)
    Q_PROPERTY(double blunderRate READ blunderRate NOTIFY resultReady)
    Q_PROPERTY(QString errorMessage READ errorMessage NOTIFY errorOccurred)

public:
    explicit AnalysisController(QObject *parent = nullptr);
    ~AnalysisController();

    QString username() const;
    void setUsername(const QString &username);

    bool isAnalyzing() const;
    double progress() const;
    QString progressText() const;

    double suspicionScore() const;
    QString riskLevel() const;
    double acplMean() const;
    int gamesCount() const;
    double top1MatchRate() const;
    double blunderRate() const;
    QString errorMessage() const;

    Q_INVOKABLE void startAnalysis(const QString &username, int games = 50);
    Q_INVOKABLE void cancelAnalysis();

signals:
    void usernameChanged();
    void isAnalyzingChanged();
    void progressChanged();
    void progressTextChanged();
    void resultReady();
    void errorOccurred();

private slots:
    void onReadyReadStandardOutput();
    void onReadyReadStandardError();
    void onProcessFinished(int exitCode, QProcess::ExitStatus exitStatus);

private:
    void processJsonLine(const QByteArray &line);
    void setIsAnalyzing(bool analyzing);
    void setProgress(double progress);
    void setProgressText(const QString &text);
    void setErrorMessage(const QString &message);
    QString findPythonPath() const;

    QProcess *m_process = nullptr;
    QByteArray m_outputBuffer;

    QString m_username;
    bool m_isAnalyzing = false;
    double m_progress = 0.0;
    QString m_progressText;

    double m_suspicionScore = 0.0;
    QString m_riskLevel;
    double m_acplMean = 0.0;
    int m_gamesCount = 0;
    double m_top1MatchRate = 0.0;
    double m_blunderRate = 0.0;
    QString m_errorMessage;
};

#endif // ANALYSISCONTROLLER_H
