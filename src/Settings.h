#ifndef SETTINGS_H
#define SETTINGS_H

#include <QObject>
#include <QQmlEngine>
#include <QSettings>

class Settings : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    Q_PROPERTY(QString pythonPath READ pythonPath WRITE setPythonPath NOTIFY pythonPathChanged)
    Q_PROPERTY(QString stockfishPath READ stockfishPath WRITE setStockfishPath NOTIFY stockfishPathChanged)
    Q_PROPERTY(int defaultGames READ defaultGames WRITE setDefaultGames NOTIFY defaultGamesChanged)
    Q_PROPERTY(int defaultDepth READ defaultDepth WRITE setDefaultDepth NOTIFY defaultDepthChanged)

public:
    explicit Settings(QObject *parent = nullptr);

    QString pythonPath() const;
    void setPythonPath(const QString &path);

    QString stockfishPath() const;
    void setStockfishPath(const QString &path);

    int defaultGames() const;
    void setDefaultGames(int games);

    int defaultDepth() const;
    void setDefaultDepth(int depth);

signals:
    void pythonPathChanged();
    void stockfishPathChanged();
    void defaultGamesChanged();
    void defaultDepthChanged();

private:
    QSettings m_settings;
};

#endif // SETTINGS_H
