package executor

import (
	"context"
	"fmt"
	"os"
	"strconv"
	"strings"
	"syscall"
	"time"
)

func readProcessIdentity(pid int) (string, uint64, error) {
	comm, err := os.ReadFile(fmt.Sprintf("/proc/%d/comm", pid))
	if err != nil {
		return "", 0, err
	}
	stat, err := os.ReadFile(fmt.Sprintf("/proc/%d/stat", pid))
	if err != nil {
		return "", 0, err
	}
	raw := string(stat)
	end := strings.LastIndexByte(raw, ')')
	if end < 0 || end+2 >= len(raw) {
		return "", 0, fmt.Errorf("invalid stat format")
	}
	fields := strings.Fields(raw[end+2:])
	if len(fields) <= 19 {
		return "", 0, fmt.Errorf("stat fields too short")
	}
	startTime, err := strconv.ParseUint(fields[19], 10, 64)
	if err != nil {
		return "", 0, err
	}
	return strings.TrimSpace(string(comm)), startTime, nil
}

func ensureProcessIdentity(pid int, expectedName string, expectedStartTime uint64) error {
	actualName, actualStartTime, err := readProcessIdentity(pid)
	if err != nil {
		return fmt.Errorf("не удалось проверить процесс %d: %w", pid, err)
	}
	if expectedName != "" && actualName != expectedName {
		return fmt.Errorf("PID %d уже принадлежит другому процессу: ожидался %s, получен %s", pid, expectedName, actualName)
	}
	if expectedStartTime > 0 && actualStartTime != expectedStartTime {
		return fmt.Errorf("PID %d переиспользован другим процессом", pid)
	}
	return nil
}

func waitProcessExit(ctx context.Context, proc *os.Process, pid int, timeout time.Duration) error {
	timer := time.NewTimer(timeout)
	ticker := time.NewTicker(150 * time.Millisecond)
	defer timer.Stop()
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-timer.C:
			return fmt.Errorf("процесс %d не завершился за %v", pid, timeout)
		case <-ticker.C:
			if err := proc.Signal(syscall.Signal(0)); err != nil {
				return nil
			}
		}
	}
}

// killProcess завершает процесс: сначала SIGTERM, затем ждёт graceful shutdown,
// и только потом использует SIGKILL как fallback. Перед этим проверяет, что PID
// всё ещё принадлежит тому же процессу, который видел UI.
func killProcess(ctx context.Context, pid int, expectedName string, expectedStartTime uint64) (string, error) {
	if IsDeniedPID(pid) {
		return "", fmt.Errorf("PID %d is in deny list", pid)
	}
	if err := ensureProcessIdentity(pid, expectedName, expectedStartTime); err != nil {
		return "", err
	}
	proc, err := os.FindProcess(pid)
	if err != nil {
		return "", fmt.Errorf("процесс %d не найден: %w", pid, err)
	}
	if err := proc.Signal(syscall.SIGTERM); err != nil {
		return "", fmt.Errorf("не удалось отправить SIGTERM процессу %d: %w", pid, err)
	}
	if err := waitProcessExit(ctx, proc, pid, 5*time.Second); err == nil {
		return "success", nil
	}
	if err := proc.Signal(syscall.SIGKILL); err != nil {
		return "", fmt.Errorf("не удалось отправить SIGKILL процессу %d: %w", pid, err)
	}
	if err := waitProcessExit(ctx, proc, pid, time.Second); err != nil {
		return "", err
	}
	return "success", nil
}

// forceKillProcess завершает процесс сразу через SIGKILL и тоже проверяет identity.
func forceKillProcess(pid int, expectedName string, expectedStartTime uint64) (string, error) {
	if IsDeniedPID(pid) {
		return "", fmt.Errorf("PID %d is in deny list", pid)
	}
	if err := ensureProcessIdentity(pid, expectedName, expectedStartTime); err != nil {
		return "", err
	}
	proc, err := os.FindProcess(pid)
	if err != nil {
		return "", fmt.Errorf("процесс %d не найден: %w", pid, err)
	}
	if err := proc.Signal(syscall.SIGKILL); err != nil {
		return "", fmt.Errorf("не удалось отправить SIGKILL процессу %d: %w", pid, err)
	}
	waitCtx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if err := waitProcessExit(waitCtx, proc, pid, time.Second); err != nil {
		return "", err
	}
	return "success", nil
}
