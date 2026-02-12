import { IsString, IsNotEmpty } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

export class AuthRequestDto {
  @ApiProperty({ description: 'Authentication token' })
  @IsString()
  @IsNotEmpty()
  token: string;
}

export class AuthResponseDto {
  @ApiProperty({ description: 'Whether authentication was successful' })
  authenticated: boolean;

  @ApiProperty({ description: 'Response message' })
  message: string;
}
