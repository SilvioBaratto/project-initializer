/** Converts the `HEALTH_HEAP_*_MB` settings into the byte limits Terminus expects. */
export const BYTES_PER_MEGABYTE = 1_048_576;

/** Keys under which each indicator appears in the health response. */
export const HEALTH_INDICATOR_KEYS = {
  database: 'database',
  memoryHeap: 'memory_heap',
} as const;
