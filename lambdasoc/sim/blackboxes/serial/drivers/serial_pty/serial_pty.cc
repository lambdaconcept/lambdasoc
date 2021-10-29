#include <cassert>
#include <fcntl.h>
#include <iostream>
#include <map>
#include <memory>
#include <poll.h>
#include <stdexcept>
#include <string>
#include <termios.h>
#include <unistd.h>
#include <util/log_fmt.h>
#include <vector>

struct pty_file {
    const int fd;

    pty_file()
            : fd(posix_openpt(O_RDWR | O_NOCTTY)) {
        if (fd < 0) {
            throw std::runtime_error(fmt_errno("posix_openpt"));
        }
    }

    ~pty_file() {
        close(fd);
    }

    void prepare() const {
        if (grantpt(fd)) {
            throw std::runtime_error(fmt_errno("grantpt"));
        }
        if (unlockpt(fd)) {
            throw std::runtime_error(fmt_errno("unlockpt"));
        }
        struct termios raw;
        if (tcgetattr(fd, &raw)) {
            throw std::runtime_error(fmt_errno("tcgetattr"));
        }
        raw.c_cflag = (raw.c_cflag & ~CSIZE) | CS8;
        raw.c_lflag &= ~(ECHO | ICANON);
        if (tcsetattr(fd, TCSANOW, &raw)) {
            throw std::runtime_error(fmt_errno("tcsetattr"));
        }
    }

    bool readable() const {
        pollfd pfd = {fd, POLLIN, 0};
        poll(&pfd, /*nfds=*/1, /*timeout=*/0);
        return (pfd.revents & POLLIN);
    }

    bool writable() const {
        pollfd pfd = {fd, POLLOUT, 0};
        poll(&pfd, /*nfds=*/1, /*timeout=*/0);
        return (pfd.revents & POLLOUT);
    }

    unsigned char read_char() const {
        unsigned char c;
        ssize_t nread = read(fd, &c, /*count=*/1);
        if (nread != 1) {
            throw std::runtime_error(fmt_errno("read"));
        }
        return c;
    }

    void write_char(unsigned char c) const {
        ssize_t nwrite = write(fd, &c, /*count=*/1);
        if (nwrite != 1) {
            throw std::runtime_error(fmt_errno("write"));
        }
    }
};

struct serial_pty;
static std::map<const std::string, std::weak_ptr<serial_pty>> serial_pty_map;

struct serial_pty {
protected:
    bool _has_rx;
    bool _has_tx;

public:
    const std::string id;
    const pty_file pty;

    serial_pty(const std::string &id)
            : _has_rx(false)
            , _has_tx(false)
            , id(id)
            , pty() {
        pty.prepare();
    }

    serial_pty() = delete;
    serial_pty(const serial_pty &) = delete;
    serial_pty &operator=(const serial_pty &) = delete;

    ~serial_pty() {
        if (serial_pty_map.count(id)) {
            serial_pty_map.erase(id);
        }
    }

    static std::shared_ptr<serial_pty> get(const std::string &id) {
        std::shared_ptr<serial_pty> desc;
        if (!serial_pty_map.count(id)) {
            desc = std::make_shared<serial_pty>(id);
            serial_pty_map[id] = desc;
        } else {
            desc = serial_pty_map[id].lock();
            assert(desc);
        }
        return desc;
    }

    void set_rx() {
        _has_rx = true;
    }
    void set_tx() {
        _has_tx = true;
    }

    bool has_rx() const {
        return _has_rx;
    }
    bool has_tx() const {
        return _has_tx;
    }
};

namespace cxxrtl_design {

// Receiver

struct serial_pty_rx : public bb_p_serial__rx</*DATA_BITS=*/8> {
    std::shared_ptr<serial_pty> desc;
    std::vector<unsigned char> buffer;

    serial_pty_rx(const std::shared_ptr<serial_pty> &desc)
            : desc(desc) {
        if (desc->has_rx()) {
            throw std::invalid_argument(fmt_msg("RX port collision"));
        }
        desc->set_rx();
    }

    void reset() override {}

    bool eval() override {
        if (posedge_p_clk()) {
            if (p_ack.get<bool>() & p_rdy.curr.get<bool>()) {
                assert(!buffer.empty());
                buffer.erase(buffer.begin());
                p_rdy.next.set<bool>(false);
            }
            if (desc->pty.readable()) {
                buffer.insert(buffer.end(), desc->pty.read_char());
            }
            if (!buffer.empty()) {
                p_rdy.next.set<bool>(true);
                p_data.next.set<unsigned char>(buffer.front());
            }
        }
        return bb_p_serial__rx</*DATA_BITS=*/8>::eval();
    }
};

template<>
std::unique_ptr<bb_p_serial__rx</*DATA_BITS=*/8>>
bb_p_serial__rx</*DATA_BITS=*/8>::create(std::string name, cxxrtl::metadata_map parameters,
        cxxrtl::metadata_map attributes) {
    assert(parameters.count("ID"));
    const std::string &id = parameters["ID"].as_string();

    std::shared_ptr<serial_pty> desc = serial_pty::get(id);
    std::cout << "Assigning '" << name << "' to " << ptsname(desc->pty.fd) << "\n";

    return std::make_unique<serial_pty_rx>(desc);
}

// Transmitter

struct serial_pty_tx : public bb_p_serial__tx</*DATA_BITS=*/8> {
    const std::shared_ptr<serial_pty> desc;

    serial_pty_tx(const std::shared_ptr<serial_pty> &desc)
            : desc(desc) {
        if (desc->has_tx()) {
            throw std::invalid_argument(fmt_msg("TX port collision"));
        }
        desc->set_tx();
    }

    void reset() override {}

    bool eval() override {
        if (posedge_p_clk()) {
            if (p_ack.get<bool>() & p_rdy.curr.get<bool>()) {
                desc->pty.write_char(p_data.get<unsigned char>());
            }
            p_rdy.next.set<bool>(desc->pty.writable());
        }
        return bb_p_serial__tx</*DATA_BITS=*/8>::eval();
    }
};

template<>
std::unique_ptr<bb_p_serial__tx</*DATA_BITS=*/8>>
bb_p_serial__tx</*DATA_BITS=*/8>::create(std::string name, cxxrtl::metadata_map parameters,
        cxxrtl::metadata_map attributes) {
    assert(parameters.count("ID"));
    const std::string &id = parameters["ID"].as_string();

    std::shared_ptr<serial_pty> desc = serial_pty::get(id);
    std::cout << "Assigning '" << name << "' to " << ptsname(desc->pty.fd) << "\n";

    return std::make_unique<serial_pty_tx>(desc);
}

} // namespace cxxrtl_design
