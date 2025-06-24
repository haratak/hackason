import { NewsletterGenerationError } from '../types';

describe('Types', () => {
  describe('NewsletterGenerationError', () => {
    it('エラーオブジェクトを正しく作成できる', () => {
      const error = new NewsletterGenerationError(
        'テストエラー',
        'TEST_ERROR',
        { detail: 'エラーの詳細' }
      );
      
      expect(error).toBeInstanceOf(Error);
      expect(error).toBeInstanceOf(NewsletterGenerationError);
      expect(error.message).toBe('テストエラー');
      expect(error.code).toBe('TEST_ERROR');
      expect(error.details).toEqual({ detail: 'エラーの詳細' });
      expect(error.name).toBe('NewsletterGenerationError');
    });

    it('詳細情報なしでもエラーを作成できる', () => {
      const error = new NewsletterGenerationError(
        'シンプルなエラー',
        'SIMPLE_ERROR'
      );
      
      expect(error.message).toBe('シンプルなエラー');
      expect(error.code).toBe('SIMPLE_ERROR');
      expect(error.details).toBeUndefined();
    });
  });
});