package executor

import (
	"context"
	"fmt"
	"net"
	"os"
	"regexp"
	"strings"
)

// Regex для имён сервисов — только латиница, цифры, дефис и подчёркивание.
// Защита от инъекции в аргументы systemctl.
var serviceNameRegex = regexp.MustCompile(`^[a-zA-Z0-9_-]+$`)

// deniedPIDs — процессы, которые нельзя убивать ни при каких условиях
var deniedPIDs = map[int]bool{
	1: true, // init/systemd — убьёшь его, убьёшь всё
}

// deniedProcessNames — имена, которые тоже нельзя трогать
var deniedProcessNames = []string{"sshd", "nullius-agent", "nullius-api"}

func init() {
	// Свой PID добавляем в deny list — агент не должен убивать сам себя
	deniedPIDs[os.Getpid()] = true
}

// ValidateIP проверяет, что строка — валидный IPv4 или IPv6 адрес
func ValidateIP(ip string) bool {
	return net.ParseIP(ip) != nil
}

// ValidateService проверяет имя сервиса: сначала по regex (защита от инъекций),
// потом по whitelist из конфига
func ValidateService(name string, allowed []string) bool {
	if !serviceNameRegex.MatchString(name) {
		return false
	}
	for _, s := range allowed {
		if s == name {
			return true
		}
	}
	return false
}

// IsDeniedPID проверяет, запрещено ли завершать процесс с данным PID.
// Кроме явного deny list, проверяет имя процесса через /proc — нельзя убить sshd,
// самого себя, или systemd-* демоны.
func IsDeniedPID(pid int) bool {
	if pid <= 0 {
		return true
	}
	if deniedPIDs[pid] {
		return true
	}
	comm, err := os.ReadFile(fmt.Sprintf("/proc/%d/comm", pid))
	if err == nil {
		name := strings.TrimSpace(string(comm))
		for _, denied := range deniedProcessNames {
			if name == denied {
				return true
			}
		}
		if strings.HasPrefix(name, "systemd-") {
			return true
		}
	}
	return false
}

// Executor выполняет команды, полученные от API-сервера через WebSocket.
// Поддерживает: block_ip, unblock_ip, kill_process, restart_service.
type Executor struct {
	AllowedServices []string
}

func New(allowedServices []string) *Executor {
	return &Executor{AllowedServices: allowedServices}
}

// Execute диспетчеризует команду. Все параметры валидируются до выполнения.
func (e *Executor) Execute(ctx context.Context, command string, params map[string]interface{}) (string, error) {
	switch command {
	case "block_ip":
		ip, _ := params["ip"].(string)
		if !ValidateIP(ip) {
			return "", fmt.Errorf("invalid ip: %s", ip)
		}
		return blockIP(ip)
	case "unblock_ip":
		ip, _ := params["ip"].(string)
		if !ValidateIP(ip) {
			return "", fmt.Errorf("invalid ip: %s", ip)
		}
		return unblockIP(ip)
	case "kill_process":
		pid, _ := params["pid"].(float64) // JSON числа приходят как float64
		if pid <= 0 {
			return "", fmt.Errorf("invalid pid: %v", params["pid"])
		}
		return killProcess(ctx, int(pid))
	case "restart_service":
		name, _ := params["name"].(string)
		if !ValidateService(name, e.AllowedServices) {
			return "", fmt.Errorf("service not in whitelist: %s", name)
		}
		return restartService(name, e.AllowedServices)
	default:
		return "", fmt.Errorf("unknown command: %s", command)
	}
}
