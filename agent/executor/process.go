package executor

import (
	"context"
	"fmt"
	"os"
	"syscall"
	"time"
)

// killProcess завершает процесс: сначала SIGTERM (даём шанс на graceful shutdown),
// через 5 секунд — SIGKILL если всё ещё жив. Контекст позволяет отменить ожидание.
func killProcess(ctx context.Context, pid int) (string, error) {
	if IsDeniedPID(pid) {
		return "", fmt.Errorf("PID %d is in deny list", pid)
	}
	proc, err := os.FindProcess(pid)
	if err != nil {
		return "", fmt.Errorf("процесс %d не найден: %w", pid, err)
	}
	if err := proc.Signal(syscall.SIGTERM); err != nil {
		return "", fmt.Errorf("не удалось отправить SIGTERM процессу %d: %w", pid, err)
	}

	// Запускаем фоновую горутину для SIGKILL-fallback
	go func() {
		timer := time.NewTimer(5 * time.Second)
		defer timer.Stop()
		select {
		case <-timer.C:
			// Проверяем, жив ли ещё процесс (Signal(0) не шлёт сигнал, только проверяет)
			if err := proc.Signal(syscall.Signal(0)); err == nil {
				proc.Signal(syscall.SIGKILL)
			}
		case <-ctx.Done():
			return
		}
	}()
	return "success", nil
}
