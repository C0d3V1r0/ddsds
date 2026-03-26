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

	// - Валидация путей конфигурации: нормализуем для защиты от path traversal
	configPath = filepath.Clean(configPath)
	secretPath = filepath.Clean(secretPath)

	cfg, err := config.Load(configPath)
	if err != nil {
		log.Fatalf("// - Ошибка загрузки конфига: %v", err)
	}

	secret, err := os.ReadFile(secretPath)
	if err != nil {
		log.Fatalf("// - Не удалось прочитать agent.key: %v", err)
	}

	// - Контекст для управления жизненным циклом горутин
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	exec := executor.New(cfg.Security.AllowedServices)

	var client *ws.Client
	client = ws.NewClient(
		cfg.Agent.ServerURL,
		strings.TrimSpace(string(secret)),
		cfg.Agent.TLSSkipVerify,
		func(id, command string, params map[string]interface{}) {
			result, execErr := exec.Execute(ctx, command, params)
			if execErr != nil {
				client.SendResult(id, "error", execErr.Error())
			} else {
				client.SendResult(id, result, "")
			}
		},
	)

	go client.Run()

	// - Сбор метрик с заданным интервалом
	go func() {
		for {
			metrics, err := collector.CollectMetrics()
			if err != nil {
				log.Printf("// - Ошибка сбора метрик: %v", err)
			} else {
				client.Send(map[string]interface{}{
					"type":      "metrics",
					"timestamp": time.Now().Unix(),
					"data":      metrics,
				})
			}
			time.Sleep(time.Duration(cfg.Agent.MetricsInterval) * time.Second)
		}
	}()

	// - Сбор статусов сервисов
	go func() {
		for {
			services, err := collector.CollectServices()
			if err != nil {
				log.Printf("// - Ошибка сбора сервисов: %v", err)
			} else {
				client.Send(map[string]interface{}{
					"type": "services",
					"data": services,
				})
			}
			time.Sleep(time.Duration(cfg.Agent.ServicesInterval) * time.Second)
		}
	}()

	// - Tail логов
	tailer := collector.NewLogTailer(cfg.Agent.LogSources)
	tailer.Start()
	go func() {
		for entry := range tailer.Entries() {
			client.Send(map[string]interface{}{
				"type":      "log_event",
				"timestamp": time.Now().Unix(),
				"data":      entry,
			})
		}
	}()

	// - Сбор процессов с настраиваемым интервалом из конфига
	go func() {
		for {
			procs, err := collector.CollectProcesses()
			if err != nil {
				log.Printf("// - Ошибка сбора процессов: %v", err)
			} else {
				client.Send(map[string]interface{}{
					"type": "processes",
					"data": procs,
				})
			}
			time.Sleep(time.Duration(cfg.Agent.ProcessesInterval) * time.Second)
		}
	}()

	// - Graceful shutdown по SIGTERM/SIGINT
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGTERM, syscall.SIGINT)
	<-sig
	log.Println("// - Остановка агента...")
	cancel()
	client.SendDisconnect()
	fmt.Println("Nullius Agent stopped")
}
