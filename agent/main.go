package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/nullius/agent/collector"
	"github.com/nullius/agent/config"
	"github.com/nullius/agent/executor"
	"github.com/nullius/agent/ws"
)

func main() {
	configPath := "/opt/nullius/config/nullius.yaml"
	secretPath := "/opt/nullius/config/agent.key"
	if len(os.Args) > 1 {
		configPath = os.Args[1]
	}
	if len(os.Args) > 2 {
		secretPath = os.Args[2]
	}

	// Нормализуем пути — защита от path traversal через аргументы
	configPath = filepath.Clean(configPath)
	secretPath = filepath.Clean(secretPath)

	cfg, err := config.Load(configPath)
	if err != nil {
		log.Fatalf("Ошибка загрузки конфига: %v", err)
	}

	secret, err := os.ReadFile(secretPath)
	if err != nil {
		log.Fatalf("Не удалось прочитать agent.key: %v", err)
	}

	// Корневой контекст — при отмене все горутины сборщиков остановятся
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	exec := executor.New(cfg.Security.AllowedServices)

	// Обработчик входящих команд от API-сервера (block_ip, kill_process и т.д.)
	var client *ws.Client
	client = ws.NewClient(
		cfg.Agent.ServerURL,
		strings.TrimSpace(string(secret)),
		cfg.Agent.TLSSkipVerify,
		func(id, command string, params map[string]interface{}) {
			result, execErr := exec.Execute(ctx, command, params)
			if execErr != nil {
				client.SendResult(id, command, params, "error", execErr.Error())
			} else {
				client.SendResult(id, command, params, result, "")
			}
		},
	)

	go client.Run()

	// Горутина сбора системных метрик (CPU, RAM, диск, сеть, load average)
	go func() {
		ticker := time.NewTicker(time.Duration(cfg.Agent.MetricsInterval) * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				metrics, err := collector.CollectMetrics()
				if err != nil {
					log.Printf("Ошибка сбора метрик: %v", err)
				} else {
					client.Send(map[string]interface{}{
						"type":      "metrics",
						"timestamp": time.Now().Unix(),
						"data":      metrics,
					})
				}
			}
		}
	}()

	// Горутина опроса systemd-сервисов (nginx, postgres, docker и т.д.)
	go func() {
		ticker := time.NewTicker(time.Duration(cfg.Agent.ServicesInterval) * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				services, err := collector.CollectServices()
				if err != nil {
					log.Printf("Ошибка сбора сервисов: %v", err)
				} else {
					client.Send(map[string]interface{}{
						"type": "services",
						"data": services,
					})
				}
			}
		}
	}()

	// Запускаем tail логов — каждый файл отслеживается отдельной горутиной
	tailer := collector.NewLogTailer(cfg.Agent.LogSources)
	tailer.Start()
	go func() {
		for entry := range tailer.Entries() {
			select {
			case <-ctx.Done():
				return
			default:
				client.Send(map[string]interface{}{
					"type":      "log_event",
					"timestamp": time.Now().Unix(),
					"data":      entry,
				})
			}
		}
	}()

	// Горутина сбора списка процессов из /proc
	go func() {
		ticker := time.NewTicker(time.Duration(cfg.Agent.ProcessesInterval) * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				procs, err := collector.CollectProcesses()
				if err != nil {
					log.Printf("Ошибка сбора процессов: %v", err)
				} else {
					client.Send(map[string]interface{}{
						"type": "processes",
						"data": procs,
					})
				}
			}
		}
	}()

	// Ждём SIGTERM/SIGINT и корректно останавливаемся
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGTERM, syscall.SIGINT)
	<-sig
	log.Println("Остановка агента...")
	cancel()
	tailer.Stop()
	client.SendDisconnect()
	client.Close()
	fmt.Println("Nullius Agent stopped")
}
