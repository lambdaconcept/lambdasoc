#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <uv.h>

#include "sram_soc.cc"

cxxrtl_design::p_top top;

uv_tty_t pts_handle;
std::vector<char> rx_buf;

struct pts_write_t {
	uv_write_t req;
	uv_buf_t   buf;
};

void alloc_cb(uv_handle_t *handle, size_t suggested_size, uv_buf_t *buf) {
	*buf = uv_buf_init((char *)malloc(suggested_size), suggested_size);
}

void rx_cb(uv_stream_t *stream, ssize_t nread, const uv_buf_t *buf) {
	if (nread < 0) {
		fprintf(stderr, "read_cb: %s\n", uv_strerror(nread));
		uv_close((uv_handle_t *)stream, NULL);
	} else if (nread > 0) {
		rx_buf.insert(rx_buf.end(), buf->base, buf->base + nread);
	}
	free(buf->base);
}

void tx_cb(uv_write_t *req, int status) {
	pts_write_t *_req = (pts_write_t *)req;
	for (int i = 0; i < _req->buf.len; i++)
		putchar(_req->buf.base[i]);
	free(_req->buf.base);
	free(_req);
}

void tick_cb(uv_idle_t *handle) {
	(void)handle;
	top.p_clk.next = value<1>{1u};
	top.step();
	top.p_clk.next = value<1>{0u};
	top.step();

	wire<8>& tx_data = top.p_data_24_1;
	wire<1>& tx_ack  = top.p_ack_24_2;
	wire<1>& tx_rdy  = top.p_rdy_24_3;
	wire<8>& rx_data = top.p_data;
	wire<1>& rx_ack  = top.p_ack;
	wire<1>& rx_rdy  = top.p_rdy;

	tx_rdy.next = value<1>{1u};
	if (tx_ack.curr) {
		pts_write_t *req = (pts_write_t *)malloc(sizeof(pts_write_t));
		req->buf = uv_buf_init((char *)malloc(1), 1);
		req->buf.base[0] = (char)tx_data.curr.data[0];
		uv_write((uv_write_t *)req, (uv_stream_t *)&pts_handle, &req->buf, 1, tx_cb);
	}

	if (rx_ack.curr && rx_rdy.curr) {
		assert(!rx_buf.empty());
		rx_buf.erase(rx_buf.begin());
		rx_rdy.next = value<1>{0u};
	}
	if (!rx_buf.empty()) {
		rx_rdy.next = value<1>{1u};
		rx_data.next = value<8>{(uint8_t)rx_buf.front()};
	}
}

int main() {
	uv_loop_t *loop = uv_default_loop();

	int pts_fd = posix_openpt(O_RDWR);
	if (pts_fd < 0) {
		perror("posix_openpt");
		return -1;
	}
	if (grantpt(pts_fd)) {
		perror("grantpt");
		return -1;
	}
	if (unlockpt(pts_fd)) {
		perror("unlockpt");
		return -1;
	}
	printf("PTS file: %s\n", ptsname(pts_fd));

	uv_tty_init(loop, &pts_handle, pts_fd, 0);
	uv_tty_set_mode(&pts_handle, UV_TTY_MODE_RAW);
	uv_read_start((uv_stream_t *)&pts_handle, alloc_cb, rx_cb);

	uv_idle_t tick_handle;
	uv_idle_init(loop, &tick_handle);
	uv_idle_start(&tick_handle, tick_cb);

	top.step();
	uv_run(loop, UV_RUN_DEFAULT);

	uv_loop_close(loop);
	uv_tty_reset_mode();
	return 0;
}
