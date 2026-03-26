package tests

import (
	"testing"

	"github.com/nullius/agent/collector"
)

// На macOS тест пропускается — CollectMetrics работает только на Linux (procfs)
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
	if len(m.Disk) == 0 {
		t.Error("disk metrics should not be empty")
	}
}
