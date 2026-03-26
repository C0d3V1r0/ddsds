package collector

import (
	"bufio"
	"fmt"
	"os"
	"runtime"
	"strconv"
	"strings"
	"sync"
)

// - Метрики CPU: общая загрузка и по ядрам
type CPUMetrics struct {
	Total float64   `json:"total"`
	Cores []float64 `json:"cores"`
}

// - Метрики RAM: общий объём, использовано, процент
type RAMMetrics struct {
	Total   uint64  `json:"total"`
	Used    uint64  `json:"used"`
	Percent float64 `json:"percent"`
}

// - Метрики диска: точка монтирования, объём, использовано
type DiskMetrics struct {
	Mount string `json:"mount"`
	Total uint64 `json:"total"`
	Used  uint64 `json:"used"`
}

// - Метрики сети: дельта принятых и отправленных байт
type NetworkMetrics struct {
	RxBytesDelta uint64 `json:"rx_bytes_delta"`
	TxBytesDelta uint64 `json:"tx_bytes_delta"`
}

// - Агрегированная структура всех метрик хоста
type Metrics struct {
	CPU     CPUMetrics     `json:"cpu"`
	RAM     RAMMetrics     `json:"ram"`
	Disk    []DiskMetrics  `json:"disk"`
	Network NetworkMetrics `json:"network"`
	LoadAvg []float64      `json:"load_avg"`
}

// - Предыдущие значения для вычисления дельты сетевого трафика, защищены мьютексом
var (
	netMu     sync.Mutex
	prevNetRx uint64
	prevNetTx uint64
)

// - Предыдущие значения CPU для вычисления дельты между замерами
var (
	cpuMu        sync.Mutex
	prevCPUTotal uint64
	prevCPUIdle  uint64
)

// - Сбор всех метрик хоста; работает только на Linux (procfs)
func CollectMetrics() (*Metrics, error) {
	if runtime.GOOS != "linux" {
		return nil, fmt.Errorf("metrics collection only supported on Linux")
	}
	cpu, err := readCPU()
	if err != nil {
		return nil, err
	}
	ram, err := readRAM()
	if err != nil {
		return nil, err
	}
	load, _ := readLoadAvg()
	net, _ := readNetwork()

	return &Metrics{
		CPU:     *cpu,
		RAM:     *ram,
		Disk:    nil,
		Network: *net,
		LoadAvg: load,
	}, nil
}

// - Чтение загрузки CPU из /proc/stat
func readCPU() (*CPUMetrics, error) {
	f, err := os.Open("/proc/stat")
	if err != nil {
		return nil, err
	}
	defer f.Close()
	scanner := bufio.NewScanner(f)
	var total float64
	var cores []float64
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "cpu ") {
			total = parseCPULine(line)
		} else if strings.HasPrefix(line, "cpu") {
			cores = append(cores, parseCPULine(line))
		}
	}
	return &CPUMetrics{Total: total, Cores: cores}, nil
}

// - Парсинг строки /proc/stat и вычисление дельты CPU между замерами
func parseCPULine(line string) float64 {
	fields := strings.Fields(line)
	if len(fields) < 5 {
		return 0
	}
	var vals []uint64
	for _, f := range fields[1:] {
		v, _ := strconv.ParseUint(f, 10, 64)
		vals = append(vals, v)
	}
	var total, idle uint64
	for i, v := range vals {
		total += v
		// - Четвёртое поле (индекс 3) — idle time
		if i == 3 {
			idle = v
		}
	}

	cpuMu.Lock()
	deltaTotal := total - prevCPUTotal
	deltaIdle := idle - prevCPUIdle
	prevCPUTotal = total
	prevCPUIdle = idle
	cpuMu.Unlock()

	// - При первом вызове или нулевой дельте возвращаем 0
	if deltaTotal == 0 {
		return 0.0
	}
	return float64(deltaTotal-deltaIdle) / float64(deltaTotal) * 100.0
}

// - Чтение информации о RAM из /proc/meminfo
func readRAM() (*RAMMetrics, error) {
	f, err := os.Open("/proc/meminfo")
	if err != nil {
		return nil, err
	}
	defer f.Close()
	info := map[string]uint64{}
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		parts := strings.Fields(scanner.Text())
		if len(parts) >= 2 {
			key := strings.TrimSuffix(parts[0], ":")
			val, _ := strconv.ParseUint(parts[1], 10, 64)
			info[key] = val
		}
	}
	total := info["MemTotal"]
	available := info["MemAvailable"]
	used := total - available
	var percent float64
	if total > 0 {
		percent = float64(used) / float64(total) * 100
	}
	// - Значения в /proc/meminfo в kB, переводим в байты
	return &RAMMetrics{Total: total * 1024, Used: used * 1024, Percent: percent}, nil
}

// - Чтение load average из /proc/loadavg
func readLoadAvg() ([]float64, error) {
	data, err := os.ReadFile("/proc/loadavg")
	if err != nil {
		return nil, err
	}
	fields := strings.Fields(string(data))
	var load []float64
	for i := 0; i < 3 && i < len(fields); i++ {
		v, _ := strconv.ParseFloat(fields[i], 64)
		load = append(load, v)
	}
	return load, nil
}

// - Чтение сетевой статистики из /proc/net/dev, вычисление дельты
func readNetwork() (*NetworkMetrics, error) {
	f, err := os.Open("/proc/net/dev")
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var totalRx, totalTx uint64
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if !strings.Contains(line, ":") {
			continue
		}
		parts := strings.Fields(strings.TrimSpace(line))
		if len(parts) < 10 {
			continue
		}
		iface := strings.TrimSuffix(parts[0], ":")
		// - Исключаем loopback-интерфейс
		if iface == "lo" {
			continue
		}
		rx, _ := strconv.ParseUint(parts[1], 10, 64)
		tx, _ := strconv.ParseUint(parts[9], 10, 64)
		totalRx += rx
		totalTx += tx
	}
	netMu.Lock()
	deltaRx := totalRx - prevNetRx
	deltaTx := totalTx - prevNetTx
	// - При первом вызове дельта неинформативна, обнуляем
	if prevNetRx == 0 {
		deltaRx = 0
		deltaTx = 0
	}
	prevNetRx = totalRx
	prevNetTx = totalTx
	netMu.Unlock()
	return &NetworkMetrics{RxBytesDelta: deltaRx, TxBytesDelta: deltaTx}, nil
}
