#include <backends/cxxrtl/cxxrtl_vcd.h>
#include <exception>
#include <fstream>
#include <getopt.h>
#include <iostream>
#include <limits>
#include <poll.h>
#include <signal.h>
#include <sstream>
#include <stdexcept>
#include <stdlib.h>
#include <string>
#include <sys/signalfd.h>
#include <util/log_fmt.h>

#ifndef CXXRTL_TOP
#define CXXRTL_TOP cxxrtl_design::p_top
#endif

struct sim_args {
    bool help            = false;
    bool trace           = false;
    std::string vcd_path = "";
    bool trace_memories  = false;
    uint64_t cycles      = sim_args::max_cycles();
    bool unknown         = false;

    sim_args(int argc, char *argv[]) {
        const option long_opts[] = {
            {"help",           no_argument,       nullptr, 'h'},
            {"cycles",         required_argument, nullptr, 'c'},
            {"trace",          required_argument, nullptr, 't'},
            {"trace-memories", no_argument,       nullptr, 'm'},
            {nullptr,          no_argument,       nullptr, 0  },
        };
        while (true) {
            const int opt = getopt_long(argc, argv, "hc:t:m", long_opts, /*longindex=*/nullptr);
            if (opt == -1) {
                break;
            }
            switch (opt) {
                case 'h':
                    help = true;
                    break;
                case 'c':
                    cycles = strtoull(optarg, /*endptr=*/nullptr, /*base=*/10);
                    if (cycles > sim_args::max_cycles()) {
                        std::stringstream msg;
                        msg << "Cycles must be a positive integer lesser than or equal to "
                            << sim_args::max_cycles();
                        throw std::out_of_range(fmt_msg(msg.str()));
                    }
                    break;
                case 't':
                    trace = true;
                    vcd_path = std::string(optarg);
                    break;
                case 'm':
                    trace_memories = true;
                    break;
                default:
                    unknown = true;
                    break;
            }
        }
    }

    static constexpr uint64_t max_cycles() {
        return std::numeric_limits<uint64_t>::max() >> 1;
    }

    static std::string usage(const std::string &name) {
        std::stringstream msg;
        msg << "Usage: " << name << " [-h] [--cycles CYCLES] [--trace VCD_PATH] [--trace-memories]\n"
            << "\n"
            << "Optional arguments:\n"
            << "  -h, --help            show this help message and exit\n"
            << "  -c, --cycles CYCLES   number of clock cycles (default: " << sim_args::max_cycles() << ")\n"
            << "  -t, --trace VCD_PATH  enable tracing to a VCD file\n"
            << "  -m, --trace-memories  also trace memories, at the cost of performance and disk usage\n";
        return msg.str();
    }
};

static pollfd sigint_pollfd() {
    sigset_t mask;
    sigemptyset(&mask);
    sigaddset(&mask, SIGINT);

    if (sigprocmask(SIG_BLOCK, &mask, /*oldset=*/nullptr) == -1) {
        throw std::runtime_error(fmt_errno("sigprocmask"));
    }

    int sfd = signalfd(/*fd=*/-1, &mask, /*flags=*/0);
    if (sfd == -1) {
        throw std::runtime_error(fmt_errno("signalfd"));
    }

    pollfd pfd = {sfd, POLLIN, 0};
    return pfd;
}

int main(int argc, char *argv[]) {
    int rc = 0;

    try {
        const sim_args args(argc, argv);

        if (args.help | args.unknown) {
            std::cout << sim_args::usage(argv[0]);
            if (args.unknown) {
                rc = 1;
            }
        } else {
            CXXRTL_TOP top;
            cxxrtl::vcd_writer vcd;
            std::ofstream vcd_file;
            debug_items debug_items;

            if (args.trace) {
                vcd_file.open(args.vcd_path);
                top.debug_info(debug_items);
                vcd.timescale(1, "us");

                if (args.trace_memories) {
                    vcd.add(debug_items);
                } else {
                    vcd.add_without_memories(debug_items);
                }
            }

            std::cout << "Press Enter to start simulation...";
            std::cin.get();

            pollfd sigint_pfd = sigint_pollfd();

            std::cout << "Running.\n"
                      << "Press Ctrl-C to exit simulation.\n";

            for (uint64_t i = 0; i < args.cycles; i++) {
                if (sigint_pfd.revents & POLLIN) {
                    break;
                }

                top.p_clk__0____io.set<bool>(false);
                top.step();
                if (args.trace) {
                    vcd.sample(2 * i);
                }
                top.p_clk__0____io.set<bool>(true);
                top.step();
                if (args.trace) {
                    vcd.sample(2 * i + 1);
                    vcd_file << vcd.buffer;
                    vcd.buffer.clear();
                }

                poll(&sigint_pfd, /*nfds=*/1, /*timeout=*/0);
            }
        }
    } catch (std::exception &e) {
        std::cout << "ERROR: " << e.what() << "\n";
        rc = 1;
    }

    std::cout << "\rExiting.\n";
    return rc;
}
