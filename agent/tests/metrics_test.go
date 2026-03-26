package tests

import (
	"testing"

	"github.com/nullius/agent/collector"
)

func TestCollectMetrics(t *testing.T) {
	m, err := collector.CollectMetrics()
	if err != nil {
		// - На macOS и других не-Linux системах тест пропускается
		t.Skipf("skipping on non-Linux: %v", err)
	}
	if m.CPU.Total < 0 || m.CPU.Total > 100 {
		t.Errorf("CPU total out of range: %f", m.CPU.Total)
	}
	if m.RAM.Total == 0 {
		t.Error("RAM total should not be 0")
	}
}
