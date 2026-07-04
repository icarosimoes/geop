// Validações de campo espelhando app/core/validators.py e app/domain/employees/schemas.py no backend,
// para dar feedback imediato no formulário sem esperar o round-trip da API.

export function onlyDigits(value: string): string {
  return value.replace(/\D/g, "");
}

export function isValidCPF(value: string): boolean {
  const digits = onlyDigits(value);
  if (digits.length !== 11 || /^(\d)\1{10}$/.test(digits)) return false;

  for (const i of [9, 10]) {
    let total = 0;
    for (let j = 0; j < i; j++) {
      total += Number(digits[j]) * (i + 1 - j);
    }
    const digit = ((total * 10) % 11) % 10;
    if (digit !== Number(digits[i])) return false;
  }
  return true;
}

export function formatCPF(value: string): string {
  const digits = onlyDigits(value).slice(0, 11);
  return digits
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

export function isValidCEP(value: string): boolean {
  return onlyDigits(value).length === 8;
}

export function formatCEP(value: string): string {
  const digits = onlyDigits(value).slice(0, 8);
  return digits.replace(/(\d{5})(\d)/, "$1-$2");
}

export function isValidBirthDate(value: string): boolean {
  if (!value) return true;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return date <= today;
}
