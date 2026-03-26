package tests

import (
	"testing"

	"github.com/nullius/agent/buffer"
)

// - проверяет базовое добавление и извлечение элементов
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

// - проверяет что при переполнении старые элементы затираются
func TestRingBufferOverflow(t *testing.T) {
	rb := buffer.New(3)
	rb.Push([]byte("a"))
	rb.Push([]byte("b"))
	rb.Push([]byte("c"))
	rb.Push([]byte("d"))

	items := rb.DrainAll()
	if len(items) != 3 {
		t.Fatalf("expected 3, got %d", len(items))
	}
	if string(items[0]) != "b" {
		t.Errorf("expected 'b', got '%s'", items[0])
	}
}

// - проверяет что после drain буфер пуст
func TestRingBufferDrainEmpties(t *testing.T) {
	rb := buffer.New(5)
	rb.Push([]byte("x"))
	rb.DrainAll()

	items := rb.DrainAll()
	if len(items) != 0 {
		t.Fatalf("expected 0 after drain, got %d", len(items))
	}
}

// - проверяет что нулевой capacity вызывает панику
func TestRingBufferZeroCapacityPanics(t *testing.T) {
	defer func() {
		r := recover()
		if r == nil {
			t.Fatal("expected panic for zero capacity, got none")
		}
	}()
	buffer.New(0)
}

// - проверяет что отрицательный capacity вызывает панику
func TestRingBufferNegativeCapacityPanics(t *testing.T) {
	defer func() {
		r := recover()
		if r == nil {
			t.Fatal("expected panic for negative capacity, got none")
		}
	}()
	buffer.New(-1)
}
