package executor

import (
	"context"
	"fmt"
	"os"
	"syscall"
	"time"
)

func killProcess(ctx context.Context, pid int) (string, error) {
	if IsDeniedPID(pid) {
		return "", fmt.Errorf("PID %d is in deny list", pid)
	}
	proc, err := os.FindProcess(pid)
	if err != nil {
		return "", fmt.Errorf("// - Процесс %d не найден: %w", pid, err)
	}
	// - SIGTERM для graceful завершения
	if err := proc.Signal(syscall.SIGTERM); err != nil {
		return "", fmt.Errorf("// - Ошибка отправки SIGTERM процессу %d: %w", pid, err)
	}
	// - Ждём 5 секунд, затем SIGKILL если процесс жив; контекст позволяет отменить ожидание
	go func() {
		timer := time.NewTimer(5 * time.Second)
		defer timer.Stop()
		select {
		case <-timer.C:
			if err := proc.Signal(syscall.Signal(0)); err == nil {
				proc.Signal(syscall.SIGKILL)
			}
		case <-ctx.Done():
			return
		}
	}()
	return "success", nil
}
