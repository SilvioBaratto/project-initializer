import { INestApplication, UnauthorizedException } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { openApiDocumentOf, responseSchemaOf } from '../../../test/support/openapi-document';
import { AUTHENTICATION_REQUIRED_MESSAGE } from './auth-messages';
import { AuthenticatedUser } from './authenticated-user';
import { CurrentUserController } from './current-user.controller';

/** Validates src/common/auth/current-user.controller.ts CurrentUserController. */
describe('CurrentUserController', () => {
  const controller = new CurrentUserController();

  it('when a user is attached, then id, email and roles are returned', () => {
    const user: AuthenticatedUser = { id: 'user-1', email: 'a@example.com', roles: ['admin'] };

    expect(controller.currentUser(user)).toEqual({
      id: 'user-1',
      email: 'a@example.com',
      roles: ['admin'],
    });
  });

  it('when the identity has no email, then the email is null', () => {
    expect(controller.currentUser({ id: 'service-1', roles: [] })).toEqual({
      id: 'service-1',
      email: null,
      roles: [],
    });
  });

  it('when no user is attached, then the request is refused with 401', () => {
    expect(() => controller.currentUser(undefined)).toThrow(
      new UnauthorizedException(AUTHENTICATION_REQUIRED_MESSAGE),
    );
  });

  describe('OpenAPI document', () => {
    let app: INestApplication;

    beforeAll(async () => {
      const moduleRef = await Test.createTestingModule({
        controllers: [CurrentUserController],
      }).compile();
      app = moduleRef.createNestApplication();
      await app.init();
    });

    afterAll(async () => {
      await app.close();
    });

    it('when GET /auth/me is documented, then its 200 body is the user info whitelist', () => {
      expect(responseSchemaOf(openApiDocumentOf(app), '/auth/me', 'get', '200')).toMatchObject({
        type: 'object',
        properties: {
          id: { type: 'string', minLength: 1 },
          email: { nullable: true },
          roles: { type: 'array', items: { type: 'string' } },
        },
        required: ['id', 'email', 'roles'],
      });
    });
  });
});
