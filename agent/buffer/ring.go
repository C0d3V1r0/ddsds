package buffer

import "sync"

// RingBuffer — потокобезопасный кольцевой буфер для сообщений.
// Используется WS-клиентом: если сервер недоступен, сообщения копятся здесь
// и отправляются при восстановлении соединения. При переполнении затирает самые старые.
type RingBuffer struct {
	mu    sync.Mutex
	items [][]byte
	head  int
	count int
	cap   int
}

// New создаёт буфер заданной ёмкости. Паникует если capacity <= 0 — это баг вызывающего кода.
func New(capacity int) *RingBuffer {
	if capacity <= 0 {
		panic("buffer capacity must be > 0")
	}
	return &RingBuffer{
		items: make([][]byte, capacity),
		cap:   capacity,
	}
}

// Push добавляет элемент. Если буфер полон — перезаписывает самый старый (FIFO с вытеснением).
func (rb *RingBuffer) Push(data []byte) {
	rb.mu.Lock()
	defer rb.mu.Unlock()

	// Буфер хранит свою копию сообщения, чтобы вызывающий код не мог
	// случайно изменить уже поставленные в очередь байты.
	clonedData := append([]byte(nil), data...)
	idx := (rb.head + rb.count) % rb.cap
	if rb.count == rb.cap {
		rb.head = (rb.head + 1) % rb.cap
	} else {
		rb.count++
	}
	rb.items[idx] = clonedData
}

// DrainAll извлекает все элементы в порядке добавления и очищает буфер.
// Вызывается при восстановлении WS-соединения.
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
