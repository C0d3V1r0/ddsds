package collector

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// - Информация о процессе: PID, имя, CPU, RAM
type ProcessInfo struct {
	PID  int     `json:"pid"`
	Name string  `json:"name"`
	CPU  float64 `json:"cpu"`
	RAM  uint64  `json:"ram"`
}

// - Сбор списка процессов из /proc
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

// - Чтение информации о процессе из /proc/<pid>/stat
func readProcessInfo(pid int) (*ProcessInfo, error) {
	statPath := filepath.Join("/proc", strconv.Itoa(pid), "stat")
	data, err := os.ReadFile(statPath)
	if err != nil {
		return nil, err
	}
	s := string(data)
	// - Имя процесса заключено в скобки: (name)
	start := strings.IndexByte(s, '(')
	end := strings.LastIndexByte(s, ')')
	if start < 0 || end < 0 {
		return nil, fmt.Errorf("invalid stat format")
	}
	name := s[start+1 : end]
	fields := strings.Fields(s[end+2:])
	var rss uint64
	// - RSS находится на позиции 23 в /proc/pid/stat (индекс 21 после имени)
	if len(fields) > 21 {
		rss, _ = strconv.ParseUint(fields[21], 10, 64)
		// - RSS в страницах, умножаем на реальный размер страницы ОС
		rss *= uint64(os.Getpagesize())
	}
	return &ProcessInfo{PID: pid, Name: name, RAM: rss}, nil
}
