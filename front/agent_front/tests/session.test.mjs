import test from 'node:test'
import assert from 'node:assert/strict'
import { newThreadId } from '../src/session.ts'

test('new chats receive distinct, nonempty thread IDs', () => {
  const first = newThreadId()
  const second = newThreadId()
  assert.match(first, /^thread-[0-9a-f-]{36}$/)
  assert.notEqual(first, second)
})
