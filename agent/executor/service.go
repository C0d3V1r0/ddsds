package executor

import (
	"fmt"
	"os/exec"
)

func restartService(name string, allowed []string) (string, error) {
	if !ValidateService(name, allowed) {
		return "", fmt.Errorf("service not in whitelist: %s", name)
	}
	cmd := exec.Command("systemctl", "restart", name)
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("restart failed: %w", err)
	}
	return "success", nil
}
