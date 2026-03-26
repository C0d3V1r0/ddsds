package executor

import (
	"fmt"
	"os/exec"
)

// blockIP добавляет правило iptables для блокировки входящего трафика от IP.
// Время жизни блокировки контролирует API-сервер через expired_at.
func blockIP(ip string) (string, error) {
	if !ValidateIP(ip) {
		return "", fmt.Errorf("invalid IP: %s", ip)
	}
	cmd := exec.Command("iptables", "-A", "INPUT", "-s", ip, "-j", "DROP")
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("iptables block failed: %w", err)
	}
	return "success", nil
}

// unblockIP удаляет правило блокировки для указанного IP
func unblockIP(ip string) (string, error) {
	if !ValidateIP(ip) {
		return "", fmt.Errorf("invalid IP: %s", ip)
	}
	cmd := exec.Command("iptables", "-D", "INPUT", "-s", ip, "-j", "DROP")
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("iptables unblock failed: %w", err)
	}
	return "success", nil
}
