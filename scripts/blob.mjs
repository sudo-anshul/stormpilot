// Narrow server-side bridge to the official Blob SDK. Credentials stay in env.
import { put, get, list, issueSignedToken, presignUrl } from '@vercel/blob';
import { createReadStream, createWriteStream } from 'node:fs';
import { mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';

export async function streamSha256(stream) {
  const hash = createHash('sha256');
  for await (const chunk of stream) hash.update(chunk);
  return hash.digest('hex');
}

export async function putVerified(key, body, expectedSha, options, api = { put, get }) {
  try {
    return await api.put(key, body, options);
  } catch (error) {
    body?.destroy?.();
    if (options.allowOverwrite) throw error;
    // A retry can encounter an existing immutable upload, including a PUT whose
    // response was lost. Success requires checking the actual stored bytes.
    let existing;
    try { existing = await api.get(key, { access: 'private', useCache: false }); }
    catch { throw error; }
    if (!existing || existing.statusCode !== 200) throw error;
    let sha;
    try { sha = await streamSha256(existing.stream); }
    catch { throw error; }
    if (sha !== expectedSha) throw new Error(`Immutable artifact conflict at ${key}: stored SHA-256 differs.`);
    return { pathname: key, reused: true };
  }
}

export async function execute(request) {
  const options = { access: 'private', addRandomSuffix: false, allowOverwrite: Boolean(request.overwrite) };
  let result;
  if (request.action === 'put_file') {
    const sha = await streamSha256(createReadStream(request.path));
    if (request.sha256 && sha !== request.sha256) throw new Error('The local artifact changed before upload.');
    const blob = await putVerified(request.key, createReadStream(request.path), sha, { ...options, contentType: request.content_type || 'application/octet-stream' });
    result = { pathname: blob.pathname };
  } else if (request.action === 'put_json') {
    const body = JSON.stringify(request.value);
    const sha = createHash('sha256').update(body).digest('hex');
    const blob = await putVerified(request.key, body, sha, { ...options, contentType: 'application/json' });
    result = { pathname: blob.pathname };
  } else if (request.action === 'get_json' || request.action === 'get_file') {
    const blob = await get(request.key, { access: 'private', useCache: false });
    if (!blob || blob.statusCode !== 200) result = null;
    else if (request.action === 'get_json') result = await new Response(blob.stream).json();
    else {
      await mkdir(dirname(request.path), { recursive: true });
      await pipeline(Readable.fromWeb(blob.stream), createWriteStream(request.path));
      result = { path: request.path };
    }
  } else if (request.action === 'list') {
    const blobs = await list({ prefix: request.prefix, limit: request.limit || 1000, ...(request.cursor ? { cursor: request.cursor } : {}) });
    result = { paths: blobs.blobs.map(blob => blob.pathname), has_more: blobs.hasMore, cursor: blobs.cursor ?? null };
  } else if (request.action === 'signed_download') {
    const validUntil = Date.now() + 5 * 60 * 1000;
    const token = await issueSignedToken({ pathname: request.key, operations: ['get'], validUntil });
    const signed = await presignUrl(token, { pathname: request.key, operation: 'get', access: 'private', validUntil, useCache: false });
    result = { url: signed.presignedUrl };
  } else throw new Error('Unsupported storage operation.');
  return result;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    let input = '';
    for await (const chunk of process.stdin) input += chunk;
    process.stdout.write(JSON.stringify(await execute(JSON.parse(input))));
  } catch (error) {
    process.stderr.write(`${error.name}: ${error.message}\n`);
    process.exitCode = 1;
  }
}
