package tests

import (
	"testing"

	"github.com/nullius/agent/buffer"
)

// Базовый сценарий: push 2 элемента, drain — должны получить оба в правильном порядке
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

// Переполнение: capacity=3, пушим 4 — самый старый ("a") должен быть затёрт
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

// После drain буфер должен быть пуст
func TestRingBufferDrainEmpties(t *testing.T) {
	rb := buffer.New(5)
	rb.Push([]byte("x"))
	rb.DrainAll()

	items := rb.DrainAll()
	if len(items) != 0 {
		t.Fatalf("expected 0 after drain, got %d", len(items))
	}
}

// Нулевой capacity — программистская ошибка, должна быть паника
func TestRingBufferZeroCapacityPanics(t *testing.T) {
	defer func() {
		r := recover()
		if r == nil {
			t.Fatal("expected panic for zero capacity, got none")
		}
	}()
	buffer.New(0)
}

// Отрицательный capacity — аналогично
func TestRingBufferNegativeCapacityPanics(t *testing.T) {
	defer func() {
		r := recover()
		if r == nil {
			t.Fatal("expected panic for negative capacity, got none")
		}
	}()
	buffer.New(-1)
}

// Буфер обязан хранить свою копию, а не ссылку на исходный слайс.
func TestRingBufferPushClonesData(t *testing.T) {
	rb := buffer.New(2)
	source := []byte("abc")

	rb.Push(source)
	source[0] = 'z'

	items := rb.DrainAll()
	if len(items) != 1 {
		t.Fatalf("expected 1 item, got %d", len(items))
	}
	if string(items[0]) != "abc" {
		t.Fatalf("expected cloned payload 'abc', got %q", string(items[0]))
	}
}
