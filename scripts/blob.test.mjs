import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { Readable } from 'node:stream';
import { putVerified } from './blob.mjs';

const options = { access: 'private', allowOverwrite: false, addRandomSuffix: false };
const sha = text => createHash('sha256').update(text).digest('hex');

test('an already-stored immutable upload is reused only after byte verification', async () => {
  const result = await putVerified('object', 'same bytes', sha('same bytes'), options, {
    put: async () => { throw new Error('already exists or response lost'); },
    get: async (key, request) => {
      assert.equal(request.useCache, false);
      return { statusCode: 200, stream: Readable.from(['same ', 'bytes']) };
    },
  });
  assert.deepEqual(result, { pathname: 'object', reused: true });
});

test('an existing object with different bytes remains an immutable conflict', async () => {
  await assert.rejects(putVerified('object', 'wanted', sha('wanted'), options, {
    put: async () => { throw new Error('already exists'); },
    get: async () => ({ statusCode: 200, stream: Readable.from(['different']) }),
  }), /stored SHA-256 differs/);
});

test('a failed upload with no stored object preserves its original failure', async () => {
  await assert.rejects(putVerified('object', 'wanted', sha('wanted'), options, {
    put: async () => { throw new Error('storage unavailable'); },
    get: async () => null,
  }), /storage unavailable/);
});

test('unread failed upload streams are closed before verification', async () => {
  const body = Readable.from(['wanted']);
  await assert.rejects(putVerified('object', body, sha('wanted'), options, {
    put: async () => { throw new Error('storage unavailable'); },
    get: async () => null,
  }));
  assert.equal(body.destroyed, true);
});
