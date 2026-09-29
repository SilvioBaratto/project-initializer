import { z } from 'zod';

export const UserInfoSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  role: z.string(),
});

export type UserInfoDto = z.infer<typeof UserInfoSchema>;
