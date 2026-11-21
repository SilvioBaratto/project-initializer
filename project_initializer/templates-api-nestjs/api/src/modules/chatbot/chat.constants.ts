/** Name of the BullMQ queue that carries asynchronous chat jobs. */
export const CHAT_QUEUE_NAME = 'chat';

/** Name every chat job is enqueued under; the processor handles exactly this job type. */
export const CHAT_JOB_NAME = 'chat';

/** Longest accepted `user_question`, in characters; bounds LLM cost per request. */
export const MAX_CHAT_QUESTION_LENGTH = 4_000;

/** Most history entries a client may send with one question. */
export const MAX_CHAT_HISTORY_MESSAGES = 50;

/**
 * Longest accepted single history entry, in characters. History includes the assistant's earlier
 * answers, which run longer than a question, so it is looser than {@link MAX_CHAT_QUESTION_LENGTH}.
 */
export const MAX_CHAT_HISTORY_MESSAGE_LENGTH = 8_000;

/** Generic message for every chat failure; the cause is logged server side, never returned. */
export const CHAT_UNAVAILABLE_MESSAGE =
  'The assistant is temporarily unavailable. Please try again later.';

/** Returned for an unknown job id and for a job that belongs to another caller alike. */
export const CHAT_JOB_NOT_FOUND_MESSAGE = 'Chat job not found';

/** Delay before the first retry of a failed chat job; BullMQ doubles it on every further attempt. */
export const CHAT_JOB_BACKOFF_DELAY_MS = 1_000;

/**
 * How long a completed chat job stays readable. This is the window a client has to poll for its
 * answer.
 */
export const COMPLETED_CHAT_JOB_TTL_SECONDS = 3_600;

/** Most completed chat jobs kept in Redis, whatever their age, so load cannot grow it unbounded. */
export const COMPLETED_CHAT_JOBS_KEPT = 1_000;

/** How long a job that failed for good stays in Redis for diagnosis. */
export const FAILED_CHAT_JOB_TTL_SECONDS = 86_400;

/**
 * Shortest gap between two log lines about the same queue connection error. Redis being down makes
 * BullMQ report the same error several times a second.
 */
export const QUEUE_ERROR_LOG_INTERVAL_MS = 30_000;
