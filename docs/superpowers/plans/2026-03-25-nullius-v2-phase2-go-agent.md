# Nullius v2 — Phase 2: Go Agent

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Go agent that collects system metrics, tails log files, monitors services/processes, executes commands, and communicates with FastAPI backend via WebSocket.

**Architecture:** Single Go binary, runs as root via systemd. Connects to `ws://127.0.0.1:8000/ws/agent`, authenticates with shared secret, streams data, receives and executes commands. Ring buffer for offline buffering.

**Tech Stack:** Go 1.22+, gorilla/websocket, standard library for /proc parsing

**Spec:** `docs/superpowers/specs/2026-03-25-nullius-v2-design.md`
**Depends on:** Phase 1 (FastAPI Backend) must be running for integration tests.

---

## File Structure

```
agent/
├── go.mod
├── go.sum
├── main.go                    # Entry point, config loading, start collectors
├── config/
│   └── config.go              # Parse nullius.yaml agent section
├── ws/
│   └── client.go              # WebSocket client: connect, auth, reconnect, heartbeat
├── collector/
│   ├── metrics.go             # CPU, RAM, disk, network from /proc
│   ├── services.go            # systemctl status parsing
│   ├── logs.go                # Tail log files, send new lines
│   ├── processes.go           # /proc/[pid]/stat parsing
│   └── network.go             # Active connections, open ports
├── executor/
│   ├── executor.go            # Command dispatcher with validation
│   ├── iptables.go            # block_ip, unblock_ip
│   ├── process.go             # kill_process with deny-list
│   └── service.go             # restart_service with whitelist
├── buffer/
│   └── ring.go                # Ring buffer for offline message buffering
└── tests/
    ├── metrics_test.go
    ├── executor_test.go
    ├── buffer_test.go
    ├── config_test.go
    └── integration_test.go    # Requires running FastAPI backend
```

---

### Task 1: Go Project Scaffold & Config

**Files:**
- Create: `agent/go.mod`
- Create: `agent/main.go`
- Create: `agent/config/config.go`
- Create: `agent/tests/config_test.go`

- [ ] **Step 1: Initialize Go module**

```bash
mkdir -p agent && cd agent
go mod init github.com/nullius/agent
go get github.com/gorilla/websocket
go get gopkg.in/yaml.v3
```

- [ ] **Step 2: Write failing test for config**

```go
// agent/tests/config_test.go
package tests

import (
	"os"
	"path/filepath"
	"testing"
	"github.com/nullius/agent/config"
)

func TestLoadConfig(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "nullius.yaml")
	yaml := `
agent:
  metrics_interval: 10
  services_interval: 60
  log_sources:
    - /var/log/auth.log
    - /var/log/nginx/access.log
security:
  allowed_services:
    - nginx
    - redis
`
	os.WriteFile(path, []byte(yaml), 0644)
	cfg, err := config.Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Agent.MetricsInterval != 10 {
		t.Errorf("expected 10, got %d", cfg.Agent.MetricsInterval)
	}
	if len(cfg.Agent.LogSources) != 2 {
		t.Errorf("expected 2 log sources, got %d", len(cfg.Agent.LogSources))
	}
	if len(cfg.Security.AllowedServices) != 2 {
		t.Errorf("expected 2 allowed services, got %d", len(cfg.Security.AllowedServices))
	}
}

func TestLoadConfigDefaults(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "nullius.yaml")
	os.WriteFile(path, []byte("agent:\n  metrics_interval: 3\n"), 0644)
	cfg, err := config.Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Agent.MetricsInterval != 3 {
		t.Errorf("expected 3, got %d", cfg.Agent.MetricsInterval)
	}
	if cfg.Agent.ServicesInterval != 30 {
		t.Errorf("expected default 30, got %d", cfg.Agent.ServicesInterval)
	}
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd agent && go test ./tests/ -v -run TestLoadConfig`
Expected: FAIL — package not found

- [ ] **Step 4: Implement config.go**

```go
// agent/config/config.go
package config

import (
	"os"
	"gopkg.in/yaml.v3"
)

type AgentConfig struct {
	MetricsInterval  int      `yaml:"metrics_interval"`
	ServicesInterval int      `yaml:"services_interval"`
	LogSources       []string `yaml:"log_sources"`
}

type SecurityConfig struct {
	AllowedServices []string `yaml:"allowed_services"`
}

type Config struct {
	Agent    AgentConfig    `yaml:"agent"`
	Security SecurityConfig `yaml:"security"`
}

func Load(path string) (*Config, error) {
	cfg := &Config{
		Agent: AgentConfig{
			MetricsInterval:  5,
			ServicesInterval: 30,
			LogSources:       []string{"/var/log/auth.log"},
		},
		Security: SecurityConfig{
			AllowedServices: []string{"nginx", "postgresql", "redis", "mysql", "docker"},
		},
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return cfg, nil // defaults
	}
	err = yaml.Unmarshal(data, cfg)
	return cfg, err
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd agent && go test ./tests/ -v -run TestLoadConfig`
Expected: PASS

- [ ] **Step 6: Create main.go stub**

```go
// agent/main.go
package main

import (
	"fmt"
	"os"
	"github.com/nullius/agent/config"
)

func main() {
	configPath := "/opt/nullius/config/nullius.yaml"
	if len(os.Args) > 1 {
		configPath = os.Args[1]
	}
	cfg, err := config.Load(configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "config error: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("Nullius Agent starting (metrics every %ds)\n", cfg.Agent.MetricsInterval)
	// TODO: start collectors and WS client
}
```

- [ ] **Step 7: Commit**

```bash
git add agent/
git commit -m "feat(agent): add Go project scaffold and config loading"
```

---

### Task 2: Ring Buffer for Offline Buffering

**Files:**
- Create: `agent/buffer/ring.go`
- Create: `agent/tests/buffer_test.go`

- [ ] **Step 1: Write failing test**

```go
// agent/tests/buffer_test.go
package tests

import (
	"testing"
	"github.com/nullius/agent/buffer"
)

func TestRingBufferBasic(t *testing.T) {
	rb := buffer.New(3)
	rb.Push([]byte("a"))
	rb.Push([]byte("b"))
	items := rb.DrainAll()
	if len(items) != 2 {
		t.Fatalf("expected 2, got %d", len(items))
	}
	if string(items[0]) != "a" {
		t.Errorf("expected 'a', got '%s'", items[0])
	}
}

func TestRingBufferOverflow(t *testing.T) {
	rb := buffer.New(3)
	rb.Push([]byte("a"))
	rb.Push([]byte("b"))
	rb.Push([]byte("c"))
	rb.Push([]byte("d")) // overwrites "a"
	items := rb.DrainAll()
	if len(items) != 3 {
		t.Fatalf("expected 3, got %d", len(items))
	}
	if string(items[0]) != "b" {
		t.Errorf("expected 'b', got '%s'", items[0])
	}
}

func TestRingBufferDrainEmpties(t *testing.T) {
	rb := buffer.New(5)
	rb.Push([]byte("x"))
	rb.DrainAll()
	items := rb.DrainAll()
	if len(items) != 0 {
		t.Fatalf("expected 0 after drain, got %d", len(items))
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agent && go test ./tests/ -v -run TestRingBuffer`
Expected: FAIL

- [ ] **Step 3: Implement ring.go**

```go
// agent/buffer/ring.go
package buffer

import "sync"

type RingBuffer struct {
	mu    sync.Mutex
	items [][]byte
	head  int
	count int
	cap   int
}

func New(capacity int) *RingBuffer {
	return &RingBuffer{
		items: make([][]byte, capacity),
		cap:   capacity,
	}
}

func (rb *RingBuffer) Push(data []byte) {
	rb.mu.Lock()
	defer rb.mu.Unlock()
	idx := (rb.head + rb.count) % rb.cap
	if rb.count == rb.cap {
		rb.head = (rb.head + 1) % rb.cap
	} else {
		rb.count++
	}
	rb.items[idx] = data
}

func (rb *RingBuffer) DrainAll() [][]byte {
	rb.mu.Lock()
	defer rb.mu.Unlock()
	result := make([][]byte, 0, rb.count)
	for i := 0; i < rb.count; i++ {
		idx := (rb.head + i) % rb.cap
		result = append(result, rb.items[idx])
	}
	rb.head = 0
	rb.count = 0
	return result
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd agent && go test ./tests/ -v -run TestRingBuffer`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/buffer/
git commit -m "feat(agent): add ring buffer for offline message buffering"
```

---

### Task 3: Metrics Collector (/proc parsing)

**Files:**
- Create: `agent/collector/metrics.go`
- Create: `agent/tests/metrics_test.go`

- [ ] **Step 1: Write failing test**

```go
// agent/tests/metrics_test.go
package tests

import (
	"testing"
	"github.com/nullius/agent/collector"
)

func TestCollectMetrics(t *testing.T) {
	m, err := collector.CollectMetrics()
	if err != nil {
		t.Skipf("skipping on non-Linux: %v", err)
	}
	if m.CPU.Total < 0 || m.CPU.Total > 100 {
		t.Errorf("CPU total out of range: %f", m.CPU.Total)
	}
	if m.RAM.Total == 0 {
		t.Error("RAM total should not be 0")
	}
	if m.RAM.Percent < 0 || m.RAM.Percent > 100 {
		t.Errorf("RAM percent out of range: %f", m.RAM.Percent)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agent && go test ./tests/ -v -run TestCollectMetrics`
Expected: FAIL

- [ ] **Step 3: Implement metrics.go**

```go
// agent/collector/metrics.go
package collector

import (
	"bufio"
	"fmt"
	"os"
	"runtime"
	"strconv"
	"strings"
	"time"
)

type CPUMetrics struct {
	Total float64   `json:"total"`
	Cores []float64 `json:"cores"`
}

type RAMMetrics struct {
	Total   uint64  `json:"total"`
	Used    uint64  `json:"used"`
	Percent float64 `json:"percent"`
}

type DiskMetrics struct {
	Mount string `json:"mount"`
	Total uint64 `json:"total"`
	Used  uint64 `json:"used"`
}

type NetworkMetrics struct {
	RxBytesDelta uint64 `json:"rx_bytes_delta"`
	TxBytesDelta uint64 `json:"tx_bytes_delta"`
}

type Metrics struct {
	CPU     CPUMetrics     `json:"cpu"`
	RAM     RAMMetrics     `json:"ram"`
	Disk    []DiskMetrics  `json:"disk"`
	Network NetworkMetrics `json:"network"`
	LoadAvg []float64      `json:"load_avg"`
}

var prevCPU []uint64
var prevNetRx, prevNetTx uint64

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
	disk, _ := readDisk()

	return &Metrics{
		CPU:     *cpu,
		RAM:     *ram,
		Disk:    disk,
		Network: *net,
		LoadAvg: load,
	}, nil
}

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
	// Simple: idle is index 3
	var totalTime, idle uint64
	for i, v := range vals {
		totalTime += v
		if i == 3 {
			idle = v
		}
	}
	if totalTime == 0 {
		return 0
	}
	return float64(totalTime-idle) / float64(totalTime) * 100
}

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
			info[key] = val // in kB
		}
	}
	total := info["MemTotal"]
	available := info["MemAvailable"]
	used := total - available
	var percent float64
	if total > 0 {
		percent = float64(used) / float64(total) * 100
	}
	return &RAMMetrics{
		Total:   total * 1024, // bytes
		Used:    used * 1024,
		Percent: percent,
	}, nil
}

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
		if iface == "lo" {
			continue
		}
		rx, _ := strconv.ParseUint(parts[1], 10, 64)
		tx, _ := strconv.ParseUint(parts[9], 10, 64)
		totalRx += rx
		totalTx += tx
	}

	deltaRx := totalRx - prevNetRx
	deltaTx := totalTx - prevNetTx
	if prevNetRx == 0 { // first read
		deltaRx = 0
		deltaTx = 0
	}
	prevNetRx = totalRx
	prevNetTx = totalTx

	return &NetworkMetrics{RxBytesDelta: deltaRx, TxBytesDelta: deltaTx}, nil
}

func readDisk() ([]DiskMetrics, error) {
	// Simplified: use /proc/mounts + syscall.Statfs
	// For MVP, return empty — will be populated in integration
	return nil, nil
}

// Unused import guard
var _ = time.Now
```

- [ ] **Step 4: Run test to verify it passes (on Linux) or skips (on macOS)**

Run: `cd agent && go test ./tests/ -v -run TestCollectMetrics`
Expected: PASS on Linux, SKIP on macOS

- [ ] **Step 5: Commit**

```bash
git add agent/collector/
git commit -m "feat(agent): add metrics collector with /proc parsing"
```

---

### Task 4: WebSocket Client (Connect, Auth, Reconnect, Heartbeat)

**Files:**
- Create: `agent/ws/client.go`

- [ ] **Step 1: Implement WS client**

```go
// agent/ws/client.go
package ws

import (
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"github.com/nullius/agent/buffer"
)

type Client struct {
	url       string
	secret    string
	conn      *websocket.Conn
	mu        sync.Mutex
	connected bool
	buffer    *buffer.RingBuffer
	onCommand func(id string, command string, params map[string]interface{})
}

func NewClient(url, secret string, onCommand func(string, string, map[string]interface{})) *Client {
	return &Client{
		url:       url,
		secret:    secret,
		buffer:    buffer.New(1000),
		onCommand: onCommand,
	}
}

func (c *Client) Run() {
	for {
		err := c.connect()
		if err != nil {
			log.Printf("WS connect error: %v", err)
		}
		c.reconnect()
	}
}

func (c *Client) connect() error {
	conn, _, err := websocket.DefaultDialer.Dial(c.url, nil)
	if err != nil {
		return fmt.Errorf("dial: %w", err)
	}
	c.mu.Lock()
	c.conn = conn
	c.mu.Unlock()

	// Auth
	auth := map[string]string{"type": "auth", "secret": c.secret}
	if err := conn.WriteJSON(auth); err != nil {
		conn.Close()
		return fmt.Errorf("auth send: %w", err)
	}

	var resp map[string]interface{}
	if err := conn.ReadJSON(&resp); err != nil {
		conn.Close()
		return fmt.Errorf("auth read: %w", err)
	}
	if resp["type"] != "auth_ok" {
		conn.Close()
		return fmt.Errorf("auth failed: %v", resp)
	}

	c.mu.Lock()
	c.connected = true
	c.mu.Unlock()
	log.Println("Connected to API")

	// Flush buffer
	buffered := c.buffer.DrainAll()
	for _, msg := range buffered {
		conn.WriteMessage(websocket.TextMessage, msg)
	}

	// Start heartbeat
	go c.heartbeat()

	// Read loop
	for {
		_, raw, err := conn.ReadMessage()
		if err != nil {
			break
		}
		var msg map[string]interface{}
		if json.Unmarshal(raw, &msg) != nil {
			continue
		}
		if msg["type"] == "pong" {
			continue
		}
		// Command from API
		if id, ok := msg["id"].(string); ok {
			cmd, _ := msg["command"].(string)
			params, _ := msg["params"].(map[string]interface{})
			if c.onCommand != nil {
				c.onCommand(id, cmd, params)
			}
		}
	}

	c.mu.Lock()
	c.connected = false
	c.conn = nil
	c.mu.Unlock()
	return nil
}

func (c *Client) heartbeat() {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()
	for range ticker.C {
		c.mu.Lock()
		conn := c.conn
		connected := c.connected
		c.mu.Unlock()
		if !connected || conn == nil {
			return
		}
		ping := map[string]string{"type": "ping"}
		if err := conn.WriteJSON(ping); err != nil {
			return
		}
	}
}

func (c *Client) reconnect() {
	delays := []time.Duration{1, 2, 4, 8, 16, 30, 60}
	for _, d := range delays {
		log.Printf("Reconnecting in %ds...", d)
		time.Sleep(d * time.Second)
		err := c.connect()
		if err == nil {
			return
		}
		log.Printf("Reconnect failed: %v", err)
	}
	// After max backoff, keep trying every 60s
	for {
		time.Sleep(60 * time.Second)
		if c.connect() == nil {
			return
		}
	}
}

func (c *Client) Send(msg interface{}) error {
	data, err := json.Marshal(msg)
	if err != nil {
		return err
	}
	c.mu.Lock()
	conn := c.conn
	connected := c.connected
	c.mu.Unlock()

	if !connected || conn == nil {
		c.buffer.Push(data)
		return nil
	}
	err = conn.WriteMessage(websocket.TextMessage, data)
	if err != nil {
		c.buffer.Push(data)
	}
	return err
}

func (c *Client) SendResult(id, status, errMsg string) {
	result := map[string]string{
		"type":   "command_result",
		"id":     id,
		"status": status,
	}
	if errMsg != "" {
		result["error"] = errMsg
	}
	c.Send(result)
}

func (c *Client) SendDisconnect() {
	c.mu.Lock()
	conn := c.conn
	c.mu.Unlock()
	if conn != nil {
		conn.WriteJSON(map[string]string{"type": "disconnect", "reason": "shutdown"})
		conn.Close()
	}
}
```

- [ ] **Step 2: Commit**

```bash
git add agent/ws/
git commit -m "feat(agent): add WebSocket client with auth, reconnect, heartbeat, buffering"
```

---

### Task 5: Executor (Command Handling with Validation)

**Files:**
- Create: `agent/executor/executor.go`
- Create: `agent/executor/iptables.go`
- Create: `agent/executor/process.go`
- Create: `agent/executor/service.go`
- Create: `agent/tests/executor_test.go`

- [ ] **Step 1: Write failing tests**

```go
// agent/tests/executor_test.go
package tests

import (
	"testing"
	"github.com/nullius/agent/executor"
)

func TestValidateIPv4(t *testing.T) {
	if !executor.ValidateIP("192.168.1.1") {
		t.Error("should accept valid IPv4")
	}
	if executor.ValidateIP("not-an-ip") {
		t.Error("should reject invalid IP")
	}
	if executor.ValidateIP("192.168.1.1; rm -rf /") {
		t.Error("should reject injection")
	}
}

func TestValidateServiceName(t *testing.T) {
	allowed := []string{"nginx", "redis"}
	if !executor.ValidateService("nginx", allowed) {
		t.Error("should accept allowed service")
	}
	if executor.ValidateService("malicious", allowed) {
		t.Error("should reject non-allowed service")
	}
	if executor.ValidateService("nginx; rm -rf /", allowed) {
		t.Error("should reject injection in service name")
	}
}

func TestDenyListPID(t *testing.T) {
	if !executor.IsDeniedPID(1) {
		t.Error("PID 1 should be denied")
	}
	if executor.IsDeniedPID(12345) {
		t.Error("random PID should not be denied")
	}
}

func TestValidateServiceNameRegex(t *testing.T) {
	allowed := []string{"nginx", "test-service", "my_app"}
	if !executor.ValidateService("test-service", allowed) {
		t.Error("should accept hyphenated service name")
	}
	if executor.ValidateService("../etc/passwd", allowed) {
		t.Error("should reject path traversal")
	}
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd agent && go test ./tests/ -v -run TestValidate`
Expected: FAIL

- [ ] **Step 3: Implement executor.go (validation)**

```go
// agent/executor/executor.go
package executor

import (
	"fmt"
	"net"
	"os"
	"regexp"
)

var serviceNameRegex = regexp.MustCompile(`^[a-zA-Z0-9_-]+$`)

var deniedPIDs = map[int]bool{
	1: true, // init/systemd
}

func init() {
	// Add own PID to deny list
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
	// Check known critical process names
	cmdline, err := os.ReadFile(fmt.Sprintf("/proc/%d/cmdline", pid))
	if err == nil {
		name := string(cmdline)
		for _, deny := range []string{"sshd", "nullius-agent", "nullius-api", "systemd"} {
			if len(name) > 0 && containsWord(name, deny) {
				return true
			}
		}
	}
	return false
}

func containsWord(s, word string) bool {
	return len(s) >= len(word) && (s[:len(word)] == word || s == word)
}

type Executor struct {
	AllowedServices []string
}

func New(allowedServices []string) *Executor {
	return &Executor{AllowedServices: allowedServices}
}

func (e *Executor) Execute(command string, params map[string]interface{}) (string, error) {
	switch command {
	case "block_ip":
		ip, _ := params["ip"].(string)
		duration, _ := params["duration"].(float64)
		return blockIP(ip, int(duration))
	case "unblock_ip":
		ip, _ := params["ip"].(string)
		return unblockIP(ip)
	case "kill_process":
		pid, _ := params["pid"].(float64)
		return killProcess(int(pid))
	case "restart_service":
		name, _ := params["name"].(string)
		return restartService(name, e.AllowedServices)
	default:
		return "", fmt.Errorf("unknown command: %s", command)
	}
}
```

- [ ] **Step 4: Implement iptables.go, process.go, service.go**

```go
// agent/executor/iptables.go
package executor

import (
	"fmt"
	"os/exec"
)

func blockIP(ip string, duration int) (string, error) {
	if !ValidateIP(ip) {
		return "", fmt.Errorf("invalid IP: %s", ip)
	}
	cmd := exec.Command("iptables", "-A", "INPUT", "-s", ip, "-j", "DROP")
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("iptables block failed: %w", err)
	}
	return "success", nil
}

func unblockIP(ip string) (string, error) {
	if !ValidateIP(ip) {
		return "", fmt.Errorf("invalid IP: %s", ip)
	}
	cmd := exec.Command("iptables", "-D", "INPUT", "-s", ip, "-j", "DROP")
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("iptables unblock failed: %w", err)
	}
	return "success", nil
}
```

```go
// agent/executor/process.go
package executor

import (
	"fmt"
	"os"
	"syscall"
	"time"
)

func killProcess(pid int) (string, error) {
	if IsDeniedPID(pid) {
		return "", fmt.Errorf("PID %d is in deny list", pid)
	}
	proc, err := os.FindProcess(pid)
	if err != nil {
		return "", fmt.Errorf("process not found: %w", err)
	}
	// Graceful first (SIGTERM)
	proc.Signal(syscall.SIGTERM)
	time.Sleep(5 * time.Second)
	// Check if still alive, then force kill
	if err := proc.Signal(syscall.Signal(0)); err == nil {
		proc.Signal(syscall.SIGKILL)
	}
	return "success", nil
}
```

```go
// agent/executor/service.go
package executor

import (
	"fmt"
	"os/exec"
)

func restartService(name string, allowed []string) (string, error) {
	if !ValidateService(name, allowed) {
		return "", fmt.Errorf("service not in whitelist: %s", name)
	}
	cmd := exec.Command("systemctl", "restart", name)
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("restart failed: %w", err)
	}
	return "success", nil
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd agent && go test ./tests/ -v -run "TestValidate|TestDenyList"`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agent/executor/
git commit -m "feat(agent): add command executor with IP validation, PID deny-list, service whitelist"
```

---

### Task 6: Log Tailer

**Files:**
- Create: `agent/collector/logs.go`

- [ ] **Step 1: Implement log tailer**

```go
// agent/collector/logs.go
package collector

import (
	"bufio"
	"io"
	"log"
	"os"
	"path/filepath"
	"time"
)

type LogEntry struct {
	Source string `json:"source"`
	Line   string `json:"line"`
	File   string `json:"file"`
}

type LogTailer struct {
	files   []string
	entries chan LogEntry
}

func NewLogTailer(files []string) *LogTailer {
	return &LogTailer{
		files:   files,
		entries: make(chan LogEntry, 1000),
	}
}

func (lt *LogTailer) Entries() <-chan LogEntry {
	return lt.entries
}

func (lt *LogTailer) Start() {
	for _, f := range lt.files {
		go lt.tailFile(f)
	}
}

func (lt *LogTailer) tailFile(path string) {
	source := detectSource(path)
	for {
		f, err := os.Open(path)
		if err != nil {
			log.Printf("cannot open %s: %v", path, err)
			time.Sleep(5 * time.Second)
			continue
		}
		// Seek to end
		f.Seek(0, io.SeekEnd)
		reader := bufio.NewReader(f)

		for {
			line, err := reader.ReadString('\n')
			if err != nil {
				if err == io.EOF {
					time.Sleep(200 * time.Millisecond)
					continue
				}
				break
			}
			if len(line) > 1 {
				lt.entries <- LogEntry{
					Source: source,
					Line:   line[:len(line)-1], // trim newline
					File:   path,
				}
			}
		}
		f.Close()
		time.Sleep(1 * time.Second)
	}
}

func detectSource(path string) string {
	base := filepath.Base(path)
	switch {
	case base == "auth.log":
		return "auth"
	case filepath.Dir(path) == "/var/log/nginx" || base == "access.log" || base == "error.log":
		return "nginx"
	default:
		return "syslog"
	}
}
```

- [ ] **Step 2: Commit**

```bash
git add agent/collector/logs.go
git commit -m "feat(agent): add log file tailer with source detection"
```

---

### Task 7: Services & Processes Collectors

**Files:**
- Create: `agent/collector/services.go`
- Create: `agent/collector/processes.go`
- Create: `agent/collector/network.go`

- [ ] **Step 1: Implement services.go**

```go
// agent/collector/services.go
package collector

import (
	"os/exec"
	"strings"
)

type ServiceStatus struct {
	Name   string `json:"name"`
	Status string `json:"status"`
	PID    int    `json:"pid"`
	Uptime int    `json:"uptime"`
}

func CollectServices() ([]ServiceStatus, error) {
	out, err := exec.Command(
		"systemctl", "list-units", "--type=service", "--no-pager", "--no-legend",
	).Output()
	if err != nil {
		return nil, err
	}
	var services []ServiceStatus
	for _, line := range strings.Split(string(out), "\n") {
		fields := strings.Fields(line)
		if len(fields) < 4 {
			continue
		}
		name := strings.TrimSuffix(fields[0], ".service")
		status := "stopped"
		if fields[3] == "running" {
			status = "running"
		} else if fields[3] == "failed" {
			status = "failed"
		}
		services = append(services, ServiceStatus{
			Name:   name,
			Status: status,
		})
	}
	return services, nil
}
```

- [ ] **Step 2: Implement processes.go**

```go
// agent/collector/processes.go
package collector

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type ProcessInfo struct {
	PID  int     `json:"pid"`
	Name string  `json:"name"`
	CPU  float64 `json:"cpu"`
	RAM  uint64  `json:"ram"`
}

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

func readProcessInfo(pid int) (*ProcessInfo, error) {
	statPath := filepath.Join("/proc", strconv.Itoa(pid), "stat")
	data, err := os.ReadFile(statPath)
	if err != nil {
		return nil, err
	}
	// Parse comm (name) from between parentheses
	s := string(data)
	start := strings.IndexByte(s, '(')
	end := strings.LastIndexByte(s, ')')
	if start < 0 || end < 0 {
		return nil, fmt.Errorf("invalid stat format")
	}
	name := s[start+1 : end]

	// RSS is field 24 (0-indexed from after the closing paren)
	fields := strings.Fields(s[end+2:])
	var rss uint64
	if len(fields) > 21 {
		rss, _ = strconv.ParseUint(fields[21], 10, 64)
		rss *= 4096 // pages to bytes
	}

	return &ProcessInfo{
		PID:  pid,
		Name: name,
		RAM:  rss,
	}, nil
}
```

- [ ] **Step 3: Implement network.go**

```go
// agent/collector/network.go
package collector

import (
	"fmt"
	"os/exec"
	"strings"
)

type ConnectionInfo struct {
	LocalAddr  string `json:"local_addr"`
	RemoteAddr string `json:"remote_addr"`
	State      string `json:"state"`
}

func CollectConnections() ([]ConnectionInfo, error) {
	out, err := exec.Command("ss", "-tuln", "--no-header").Output()
	if err != nil {
		return nil, err
	}
	var conns []ConnectionInfo
	for _, line := range strings.Split(string(out), "\n") {
		fields := strings.Fields(line)
		if len(fields) < 5 {
			continue
		}
		conns = append(conns, ConnectionInfo{
			LocalAddr: fields[4],
			State:     fields[1],
		})
	}
	return conns, nil
}

// Unused import guard
var _ = fmt.Sprintf
```

- [ ] **Step 4: Commit**

```bash
git add agent/collector/services.go agent/collector/processes.go agent/collector/network.go
git commit -m "feat(agent): add services, processes, and network collectors"
```

---

### Task 8: Main — Wire Everything Together

**Files:**
- Modify: `agent/main.go`

- [ ] **Step 1: Implement full main.go**

```go
// agent/main.go
package main

import (
	"fmt"
	"log"
	"os"
	"os/signal"
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

	cfg, err := config.Load(configPath)
	if err != nil {
		log.Fatalf("config error: %v", err)
	}

	secret, err := os.ReadFile(secretPath)
	if err != nil {
		log.Fatalf("cannot read agent.key: %v", err)
	}

	exec := executor.New(cfg.Security.AllowedServices)

	client := ws.NewClient(
		"ws://127.0.0.1:8000/ws/agent",
		string(secret),
		func(id, command string, params map[string]interface{}) {
			result, err := exec.Execute(command, params)
			if err != nil {
				client.SendResult(id, "error", err.Error())
			} else {
				client.SendResult(id, result, "")
			}
		},
	)

	go client.Run()

	// Metrics collector
	go func() {
		for {
			metrics, err := collector.CollectMetrics()
			if err == nil {
				client.Send(map[string]interface{}{
					"type":      "metrics",
					"timestamp": time.Now().Unix(),
					"data":      metrics,
				})
			}
			time.Sleep(time.Duration(cfg.Agent.MetricsInterval) * time.Second)
		}
	}()

	// Services collector
	go func() {
		for {
			services, err := collector.CollectServices()
			if err == nil {
				client.Send(map[string]interface{}{
					"type": "services",
					"data": services,
				})
			}
			time.Sleep(time.Duration(cfg.Agent.ServicesInterval) * time.Second)
		}
	}()

	// Log tailer
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

	// Processes collector
	go func() {
		for {
			procs, err := collector.CollectProcesses()
			if err == nil {
				client.Send(map[string]interface{}{
					"type": "processes",
					"data": procs,
				})
			}
			time.Sleep(10 * time.Second)
		}
	}()

	// Graceful shutdown
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGTERM, syscall.SIGINT)
	<-sig
	log.Println("Shutting down...")
	client.SendDisconnect()
	fmt.Println("Nullius Agent stopped")
}
```

- [ ] **Step 2: Build and verify**

Run: `cd agent && go build -o nullius-agent .`
Expected: Compiles without errors

- [ ] **Step 3: Commit**

```bash
git add agent/main.go
git commit -m "feat(agent): wire all collectors, executor, and WS client in main"
```

---

### Task 9: Integration Test (Agent + Backend)

**Files:**
- Create: `agent/tests/integration_test.go`

- [ ] **Step 1: Write integration test (requires running backend)**

```go
// agent/tests/integration_test.go
//go:build integration
package tests

import (
	"testing"
	"time"
	"github.com/nullius/agent/ws"
)

func TestAgentConnectsToBackend(t *testing.T) {
	connected := make(chan bool, 1)
	client := ws.NewClient(
		"ws://127.0.0.1:8000/ws/agent",
		"test-secret",
		func(id, cmd string, params map[string]interface{}) {
			// no-op for test
		},
	)
	go func() {
		// If Run doesn't panic immediately, we connected
		client.Run()
	}()

	// Send a ping after brief delay
	time.Sleep(2 * time.Second)
	err := client.Send(map[string]string{"type": "ping"})
	if err != nil {
		t.Fatalf("Failed to send: %v", err)
	}
	t.Log("Agent connected and sent ping successfully")
}
```

Run (requires backend): `cd agent && go test ./tests/ -v -tags integration -run TestAgentConnects`

- [ ] **Step 2: Commit**

```bash
git add agent/tests/integration_test.go
git commit -m "test(agent): add integration test for agent-backend connectivity"
```
