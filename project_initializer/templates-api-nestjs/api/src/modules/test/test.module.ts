import { Module } from '@nestjs/common';
import { TestController } from './test.controller';

/** Hosts the smoke-test routes; it has no providers because it reads no state. */
@Module({ controllers: [TestController] })
export class TestModule {}
