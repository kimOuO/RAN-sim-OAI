export type AsyncStatus = 'idle' | 'loading' | 'success' | 'error';
export interface AsyncState<T> { data: T | null; status: AsyncStatus; error: Error | null; refetch: () => Promise<T | null>; }
export interface ApiSuccess<T> { success: true; message: string; data: T; }
export interface ApiError { success: false; message: string; errors?: unknown; }
export type ApiResponse<T> = ApiSuccess<T> | ApiError;
export type Vec3 = [number, number, number];
