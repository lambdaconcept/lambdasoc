#ifndef _FMT_LOG_H
#define _FMT_LOG_H
#include <cerrno>
#include <cstring>
#include <sstream>
#include <string>

static inline std::stringstream _fmt_msg(const std::string &msg, const std::string &file,
        unsigned line) {
    std::stringstream ss;
    ss << msg << " (" << file << ":" << line << ")";
    return ss;
}

static inline std::stringstream _fmt_errno(const std::string &msg, unsigned saved_errno,
        const std::string &file, unsigned line) {
    return _fmt_msg(msg + ": " + strerror(saved_errno), file, line);
}

#define fmt_msg(msg)   _fmt_msg(msg, __FILE__, __LINE__).str()
#define fmt_errno(msg) _fmt_errno(msg, errno, __FILE__, __LINE__).str()

#endif // _FMT_LOG_H
