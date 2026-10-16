import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/api/learningStream.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } });
const { consumeLearningStream } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

function bytes(text, chunkSize = 1) {
  const encoded = new TextEncoder().encode(text);
  return new ReadableStream({ start(controller) {
    for (let offset = 0; offset < encoded.length; offset += chunkSize) controller.enqueue(encoded.slice(offset, offset + chunkSize));
    controller.close();
  } });
}

test("split UTF-8 and CRLF preserve Chinese final answer", async () => {
  const events = [];
  await consumeLearningStream(bytes('event: run.started\r\ndata: {"run_id":"r1"}\r\n\r\nevent: run.completed\r\ndata: {"answer":"课程讲解"}\r\n\r\n'), event => events.push(event));
  assert.equal(events.length, 2);
  assert.equal(events[1].data.answer, "课程讲解");
});

test("premature EOF cannot look like completion", async () => {
  await assert.rejects(consumeLearningStream(bytes('event: run.started\ndata: {}\n\n'), () => {}), /stream_incomplete/);
});

test("pending review is a terminal pause without answer", async () => {
  const events = [];
  await consumeLearningStream(bytes(': keepalive\n\nevent: review.required\ndata: {"reason":"learning_content_review"}\n\n', 8), event => events.push(event));
  assert.equal(events.length, 1);
  assert.equal(events[0].data.answer, undefined);
});

test("malformed event JSON fails instead of hiding dropped content", async () => {
  await assert.rejects(consumeLearningStream(bytes('event: run.completed\ndata: not-json\n\n'), () => {}), SyntaxError);
});

test("failure is terminal and extra content is rejected", async () => {
  const events = [];
  await consumeLearningStream(bytes('event: run.failed\ndata: {"error":"run_timeout"}\n\n'), event => events.push(event));
  assert.equal(events[0].data.error, "run_timeout");
  await assert.rejects(consumeLearningStream(bytes('event: run.failed\ndata: {}\n\nevent: answer.delta\ndata: {"delta":"x"}\n\n'), () => {}), /event_after_terminal/);
});
