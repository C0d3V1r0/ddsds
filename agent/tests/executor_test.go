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
