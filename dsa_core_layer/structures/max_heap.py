# max_heap.py — select the best K records without sorting the full input.
# Idea: keep the highest-priority record at the root, then remove it K times.
# Time: O(N + K log N). Space: O(N) for the working copy.

# key[0]: score
# key[1]: exercise["n_groups"]
# key[2]: exercise["id"]
def is_better(item_a, item_b):
    # Compare score first, then muscle coverage, then the smaller exercise id.
    key_a = item_a[0]
    key_b = item_b[0]

    if key_a[0] > key_b[0]:
        return True
    if key_a[0] < key_b[0]:
        return False

    if key_a[1] > key_b[1]:
        return True
    if key_a[1] < key_b[1]:
        return False

    return key_a[2] < key_b[2]

def sift_down(items, index, size):
    # Keep moving the item down while one of its children has a higher priority.
    while True:
        left_child = 2 * index + 1
        right_child = 2 * index + 2
        biggest = index
        if left_child < size and is_better(items[left_child], items[biggest]):
            biggest = left_child
        if right_child < size and is_better(items[right_child], items[biggest]):
            biggest = right_child
        if biggest == index:
            break
        items[index], items[biggest] = items[biggest], items[index]
        index = biggest

def build_heap(items):
    # Repair parents from the last parent back to the root.
    index = len(items) // 2 - 1
    while index >= 0:
        sift_down(items, index, len(items))
        index -= 1

def get_top_k(items, count):
    heap = list(items)
    build_heap(heap)
    size = len(heap)
    result = []
    # Extract the root repeatedly until K results are collected or the heap is empty.
    while len(result) < count and size > 0:
        result.append(heap[0])
        heap[0] = heap[size - 1]
        size -= 1
        sift_down(heap, 0, size)
    return result
