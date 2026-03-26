package collector

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
)

// ProcessInfo — информация о процессе для отправки на сервер
type ProcessInfo struct {
	PID  int     `json:"pid"`
	Name string  `json:"name"`
	CPU  float64 `json:"cpu"`
	RAM  uint64  `json:"ram"`
}

// CLK_TCK вызываем через getconf один раз за весь runtime — это syscall, незачем дёргать каждый тик
var (
	clockTicksOnce sync.Once
	clockTicks     float64 = 100
)

// CollectProcesses обходит /proc и собирает список процессов с CPU% и RSS.
// Процессы, которые не удалось прочитать (уже завершились, нет прав), тихо пропускаются.
func CollectProcesses() ([]ProcessInfo, error) {
	entries, err := os.ReadDir("/proc")
	if err != nil {
		return nil, err
	}
	var procs []ProcessInfo
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		pid, err := strconv.Atoi(e.Name())
		if err != nil {
			continue
		}
		info, err := readProcessInfo(pid)
		if err != nil {
			continue
		}
		procs = append(procs, *info)
	}
	return procs, nil
}

// readProcessInfo парсит /proc/<pid>/stat для извлечения имени, CPU% и RSS.
// Имя процесса в stat заключено в скобки: "1 (systemd) S 0 1 1 ..."
// CPU% считаем как (utime+stime)/elapsed — среднее за всё время жизни процесса.
func readProcessInfo(pid int) (*ProcessInfo, error) {
	statPath := filepath.Join("/proc", strconv.Itoa(pid), "stat")
	data, err := os.ReadFile(statPath)
	if err != nil {
		return nil, err
	}
	s := string(data)

	// Парсим имя — оно в скобках, может содержать пробелы и другие скобки
	start := strings.IndexByte(s, '(')
	end := strings.LastIndexByte(s, ')')
	if start < 0 || end < 0 {
		return nil, fmt.Errorf("invalid stat format")
	}
	name := s[start+1 : end]
	fields := strings.Fields(s[end+2:])

	var rss uint64
	var cpu float64

	// RSS — поле 23 в /proc/pid/stat (индекс 21 относительно полей после имени)
	if len(fields) > 21 {
		rss, _ = strconv.ParseUint(fields[21], 10, 64)
		rss *= uint64(os.Getpagesize()) // из страниц в байты
	}

	// CPU% = (utime + stime) / elapsed_seconds / CLK_TCK * 100
	if len(fields) > 19 {
		utime, _ := strconv.ParseUint(fields[11], 10, 64)
		stime, _ := strconv.ParseUint(fields[12], 10, 64)
		startTime, _ := strconv.ParseUint(fields[19], 10, 64)

		uptimeSeconds, err := readUptimeSeconds()
		if err == nil {
			ticks := getClockTicks()
			elapsed := uptimeSeconds - (float64(startTime) / ticks)
			if elapsed > 0 {
				cpu = ((float64(utime+stime) / ticks) / elapsed) * 100.0
			}
		}
	}
	return &ProcessInfo{PID: pid, Name: name, CPU: cpu, RAM: rss}, nil
}

func readUptimeSeconds() (float64, error) {
	f, err := os.Open("/proc/uptime")
	if err != nil {
		return 0, err
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	if !scanner.Scan() {
		return 0, fmt.Errorf("failed to read /proc/uptime")
	}
	fields := strings.Fields(scanner.Text())
	if len(fields) == 0 {
		return 0, fmt.Errorf("invalid /proc/uptime format")
	}
	return strconv.ParseFloat(fields[0], 64)
}

func getClockTicks() float64 {
	clockTicksOnce.Do(func() {
		out, err := exec.Command("getconf", "CLK_TCK").Output()
		if err != nil {
			return
		}
		value, parseErr := strconv.ParseFloat(strings.TrimSpace(string(out)), 64)
		if parseErr == nil && value > 0 {
			clockTicks = value
		}
	})
	return clockTicks
}
