import React, { useState } from 'react';
import { postComment } from '../api/comments';
import { validateText } from '../utils/validate';

interface CommentFormProps {
  postId: number;
  onSubmit: () => void;
}

function CommentForm({ postId, onSubmit }: CommentFormProps) {
  const [text, setText] = useState<string>('');
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!validateText(text)) {
      return;
    }
    await postComment(postId, text);
    setText('');
    onSubmit();
  };
  return (
    <form onSubmit={handleSubmit}>
      <textarea value={text} onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setText(e.target.value)} />
      <button type="submit">등록</button>
    </form>
  );
}

export default CommentForm;