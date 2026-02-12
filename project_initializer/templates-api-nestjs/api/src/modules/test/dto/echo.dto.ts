import { IsString, IsNotEmpty } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

export class EchoRequestDto {
  @ApiProperty({ description: 'Message to echo' })
  @IsString()
  @IsNotEmpty()
  message: string;
}

export class EchoResponseDto {
  @ApiProperty({ description: 'Echoed message' })
  message: string;
}
