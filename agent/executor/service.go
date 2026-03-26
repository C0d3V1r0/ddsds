package executor

import (
	"fmt"
	"os/exec"
)

// restartService рестартит systemd-сервис по имени. Имя обязательно проходит
// валидацию по regex и whitelist до вызова — без этого можно было бы подсунуть
// что-то вроде "nginx; rm -rf /".
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
