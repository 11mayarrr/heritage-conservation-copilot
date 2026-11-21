// قوائم المواد والأدوات: كل عنصر في سطر مستقل.
// الفاصلة مسموحة داخل اسم العنصر نفسه، مثل «مونة طينية جديدة (طين، رمل، ماء)»،
// ولهذا لا نفصل العناصر بالفاصلة أبدًا.

export const joinList = (items: string[]): string => items.join("\n");

export const splitList = (text: string): string[] =>
  text
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
