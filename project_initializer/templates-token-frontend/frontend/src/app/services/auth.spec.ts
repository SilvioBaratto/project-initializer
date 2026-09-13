/**
 * Tests for the token AuthService's storage handling. A browser that blocks site data throws a
 * SecurityError from localStorage; the service must read that as signed out and keep working,
 * because the auth guard and interceptor inject it on the first navigation and request.
 */
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { vi } from 'vitest';
import { environment } from '../../environments/environment';
import { AuthResponse, AuthService } from './auth';

const TOKEN_KEY = 'app_auth_token';

describe('AuthService storage', () => {
  function createService(): AuthService {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    return TestBed.inject(AuthService);
  }

  function blockStorage(method: 'getItem' | 'setItem' | 'removeItem'): void {
    vi.spyOn(Storage.prototype, method).mockImplementation(() => {
      throw new DOMException('The operation is insecure.', 'SecurityError');
    });
  }

  beforeEach(() => localStorage.clear());

  afterEach(() => vi.restoreAllMocks());

  it('when a token is stored, the service starts signed in', () => {
    localStorage.setItem(TOKEN_KEY, 'stored-token');
    const service = createService();

    expect(service.isAuthenticated()).toBe(true);
    expect(service.getToken()).toBe('stored-token');
  });

  it('when reading localStorage throws, the service is created signed out', () => {
    blockStorage('getItem');
    // Guards against a vacuous pass: storage really throws in this test.
    expect(() => localStorage.getItem(TOKEN_KEY)).toThrow();

    let service: AuthService | undefined;
    expect(() => (service = createService())).not.toThrow();
    expect(service?.isAuthenticated()).toBe(false);
    expect(service?.getToken()).toBeNull();
  });

  it('when writing localStorage throws, an accepted token still signs the user in', () => {
    const service = createService();
    const http = TestBed.inject(HttpTestingController);
    blockStorage('setItem');
    expect(() => localStorage.setItem(TOKEN_KEY, 'x')).toThrow();

    let response: AuthResponse | undefined;
    service.login('valid-token').subscribe((r) => (response = r));
    http
      .expectOne(`${environment.apiUrl}auth/validate`)
      .flush({ authenticated: true, message: 'Token is valid' });

    expect(response?.authenticated).toBe(true);
    expect(service.isAuthenticated()).toBe(true);
    http.verify();
  });

  it('when removing from localStorage throws, signing out still clears the session', () => {
    localStorage.setItem(TOKEN_KEY, 'stored-token');
    const service = createService();
    blockStorage('removeItem');
    expect(() => localStorage.removeItem(TOKEN_KEY)).toThrow();

    expect(() => service.logout()).not.toThrow();
    expect(service.isAuthenticated()).toBe(false);
  });
});
