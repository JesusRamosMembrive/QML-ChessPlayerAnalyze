#include "Settings.h"

Settings::Settings(QObject *parent)
    : QObject(parent)
    , m_settings(QStringLiteral("ChessAnalyzerQML"), QStringLiteral("ChessAnalyzerQML"))
{
}

QString Settings::pythonPath() const
{
    return m_settings.value(QStringLiteral("python/path"), QStringLiteral("python")).toString();
}

void Settings::setPythonPath(const QString &path)
{
    if (pythonPath() != path) {
        m_settings.setValue(QStringLiteral("python/path"), path);
        emit pythonPathChanged();
    }
}

QString Settings::stockfishPath() const
{
    return m_settings.value(QStringLiteral("stockfish/path"), QStringLiteral("stockfish")).toString();
}

void Settings::setStockfishPath(const QString &path)
{
    if (stockfishPath() != path) {
        m_settings.setValue(QStringLiteral("stockfish/path"), path);
        emit stockfishPathChanged();
    }
}

int Settings::defaultGames() const
{
    return m_settings.value(QStringLiteral("analysis/defaultGames"), 50).toInt();
}

void Settings::setDefaultGames(int games)
{
    if (defaultGames() != games) {
        m_settings.setValue(QStringLiteral("analysis/defaultGames"), games);
        emit defaultGamesChanged();
    }
}

int Settings::defaultDepth() const
{
    return m_settings.value(QStringLiteral("analysis/defaultDepth"), 12).toInt();
}

void Settings::setDefaultDepth(int depth)
{
    if (defaultDepth() != depth) {
        m_settings.setValue(QStringLiteral("analysis/defaultDepth"), depth);
        emit defaultDepthChanged();
    }
}
