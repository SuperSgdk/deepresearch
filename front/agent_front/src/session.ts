/** A fresh ID separates each chat's messages and workflow checkpoints. */
export const newThreadId = (): string => `thread-${crypto.randomUUID()}`
