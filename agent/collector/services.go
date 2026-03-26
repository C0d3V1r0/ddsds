package collector

import (
	"os/exec"
	"strings"
)

// - Статус systemd-сервиса
type ServiceStatus struct {
	Name   string `json:"name"`
	Status string `json:"status"`
	PID    int    `json:"pid"`
	Uptime int    `json:"uptime"`
}

// - Сбор списка сервисов через systemctl
func CollectServices() ([]ServiceStatus, error) {
	out, err := exec.Command(
		"systemctl", "list-units", "--type=service", "--no-pager", "--no-legend",
	).Output()
	if err != nil {
		return nil, err
	}
	var services []ServiceStatus
	for _, line := range strings.Split(string(out), "\n") {
		fields := strings.Fields(line)
		if len(fields) < 4 {
			continue
		}
		name := strings.TrimSuffix(fields[0], ".service")
		status := "stopped"
		if fields[3] == "running" {
			status = "running"
		} else if fields[3] == "failed" {
			status = "failed"
		}
		services = append(services, ServiceStatus{Name: name, Status: status})
	}
	return services, nil
}
