package executor

import (
	"context"
	"fmt"
	"net"
	"os"
	"regexp"
	"strings"
)

var serviceNameRegex = regexp.MustCompile(`^[a-zA-Z0-9_-]+$`)

var deniedPIDs = map[int]bool{
	1: true,
}

// - Имена процессов, которые запрещено завершать
var deniedProcessNames = []string{"sshd", "nullius-agent", "nullius-api"}

func init() {
	deniedPIDs[os.Getpid()] = true
}

func ValidateIP(ip string) bool {
	return net.ParseIP(ip) != nil
}

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

func IsDeniedPID(pid int) bool {
	if pid <= 0 {
		return true
	}
	if deniedPIDs[pid] {
		return true
	}
	// - Проверка имени процесса через /proc
	comm, err := os.ReadFile(fmt.Sprintf("/proc/%d/comm", pid))
	if err == nil {
		name := strings.TrimSpace(string(comm))
		for _, denied := range deniedProcessNames {
			if name == denied {
				return true
			}
		}
		// - Проверка systemd-* префикса
		if strings.HasPrefix(name, "systemd-") {
			return true
		}
	}
	return false
}

type Executor struct {
	AllowedServices []string
}

func New(allowedServices []string) *Executor {
	return &Executor{AllowedServices: allowedServices}
}

func (e *Executor) Execute(ctx context.Context, command string, params map[string]interface{}) (string, error) {
	switch command {
	case "block_ip":
		ip, _ := params["ip"].(string)
		return blockIP(ip)
	case "unblock_ip":
		ip, _ := params["ip"].(string)
		return unblockIP(ip)
	case "kill_process":
		pid, _ := params["pid"].(float64)
		return killProcess(ctx, int(pid))
	case "restart_service":
		name, _ := params["name"].(string)
		return restartService(name, e.AllowedServices)
	default:
		return "", fmt.Errorf("unknown command: %s", command)
	}
}
