import { Injectable, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createClient, SupabaseClient } from '@supabase/supabase-js';

@Injectable()
export class AuthService {
  private readonly supabase: SupabaseClient;

  constructor(private readonly configService: ConfigService) {
    const supabaseUrl = this.configService.getOrThrow<string>('SUPABASE_URL');
    const supabaseKey = this.configService.getOrThrow<string>('SUPABASE_PUBLISHABLE_KEY');
    this.supabase = createClient(supabaseUrl, supabaseKey);
  }

  async getUser(jwt: string): Promise<{ id: string; email: string; role: string }> {
    const { data, error } = await this.supabase.auth.getUser(jwt);

    if (error || !data.user) {
      throw new UnauthorizedException('Invalid or expired token');
    }

    return {
      id: data.user.id,
      email: data.user.email ?? '',
      role: data.user.role ?? 'authenticated',
    };
  }
}
