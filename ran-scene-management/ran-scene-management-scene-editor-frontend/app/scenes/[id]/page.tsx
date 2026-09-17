import { redirect } from 'next/navigation';

/** 舊網址相容:場景頁拆成四個步驟,預設進第 1 步 */
export default async function SceneEditorIndex({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/scenes/${id}/environment`);
}
