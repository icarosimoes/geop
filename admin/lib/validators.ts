// Validações de campo espelhando app/core/validators.py no backend,
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

export function isValidCNPJ(value: string): boolean {
  const digits = onlyDigits(value);
  if (digits.length !== 14 || /^(\d)\1{13}$/.test(digits)) return false;

  const weights = [
    [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
    [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
  ];
  for (const [i, w] of [[12, weights[0]], [13, weights[1]]] as [number, number[]][]) {
    let total = 0;
    for (let j = 0; j < i; j++) total += Number(digits[j]) * w[j];
    let digit = 11 - (total % 11);
    if (digit >= 10) digit = 0;
    if (digit !== Number(digits[i])) return false;
  }
  return true;
}

export function formatCNPJ(value: string): string {
  const digits = onlyDigits(value).slice(0, 14);
  return digits
    .replace(/(\d{2})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1/$2")
    .replace(/(\d{4})(\d{1,2})$/, "$1-$2");
}

export function formatCpfCnpj(value: string): string {
  const digits = onlyDigits(value);
  return digits.length > 11 ? formatCNPJ(digits) : formatCPF(digits);
}

export function isValidCEP(value: string): boolean {
  return onlyDigits(value).length === 8;
}

export function formatCEP(value: string): string {
  const digits = onlyDigits(value).slice(0, 8);
  return digits.replace(/(\d{5})(\d)/, "$1-$2");
}
