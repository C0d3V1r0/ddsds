package collector

import (
	"os/exec"
	"strings"
)

// - Информация о сетевом соединении
type ConnectionInfo struct {
	LocalAddr  string `json:"local_addr"`
	RemoteAddr string `json:"remote_addr"`
	State      string `json:"state"`
}

// - Сбор активных соединений через ss
func CollectConnections() ([]ConnectionInfo, error) {
	out, err := exec.Command("ss", "-tuln", "--no-header").Output()
	if err != nil {
		return nil, err
	}
	var conns []ConnectionInfo
	for _, line := range strings.Split(string(out), "\n") {
		fields := strings.Fields(line)
		if len(fields) < 5 {
			continue
		}
		conns = append(conns, ConnectionInfo{
			LocalAddr: fields[4],
			State:     fields[1],
		})
	}
	return conns, nil
}
