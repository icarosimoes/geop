export type HistoryEntry = {
  type: "comment" | "change" | "create";
  user: string;
  date: string;
  message?: string;
  changes?: string;
};

export type ModuleRecord = {
  id: number;
  title: string;
  category: string;
  owner: string;
  status: string;
  updatedAt: string;
  description?: string;
  history?: HistoryEntry[];
  requestType?: string;
  reservationNumber?: string;
  invoiceNumber?: string;
  checkoutDate?: string;
  taxpayerDoc?: string;
  taxpayerName?: string;
  taxpayerAddress?: string;
  taxpayerEmail?: string;
  cancellationReason?: string;
  correction?: string;
  attachments?: { name: string; url: string; type: string }[];
  slaDeadline?: string;
  apartment?: string;
  notifyUsers?: string[];
  notifyUserObjects?: { id: number; name: string }[];
  notifyUserIds?: number[];
  phone?: string;
  deadline?: string;
  location?: string;
  slaStatus?: string;
  priority?: string;
  scheduledAt?: string;
  shiftDate?: string;
  shiftType?: string;
  supervisor?: string;
  occupation?: string;
  average_daily?: string;
  guests?: number;
  uhs?: number;
  maintenance_count?: number;
  cleaning?: number;
  walk_in?: number;
  input_quantity?: number;
  output_quantity?: number;
  return_of_customers?: number;
  observations?: string;
  notes_ab?: string;
  notes_reception?: string;
  notes_reservations?: string;
  notes_governance?: string;
  notes_maintenance?: string;
  notes_ti?: string;
  notes_security?: string;
  roleId?: number;
  jobTitle?: string;
  sectorName?: string;
  avatarUrl?: string;
  sectorId?: number;
  latitude?: number | null;
  longitude?: number | null;
  geofenceRadiusM?: number | null;
  unit?: string;
  comments?: string;
  participants?: { id: number; name: string }[];
};

export type ModuleDefinition = {
  slug: string;
  title: string;
  description: string;
  singular: string;
  action: string;
  layout?: "table" | "cards" | "settings" | "profile" | "kanban" | "company";
  source?: "local" | "api";
  records: ModuleRecord[];
  serverPagination?: {
    total: number;
    page: number;
    pageSize: number;
    search?: string;
  };
  extraData?: {
    roles?: { id: number; name: string }[];
    sectors?: { id: number; name: string }[];
  };
};

const today = "19/06/2026";

export const moduleDefinitions: Record<string, ModuleDefinition> = {
  reunioes: {
    slug: "reunioes", title: "Reuniões", singular: "reunião", action: "Agendar reunião",
    description: "Organize pautas, participantes, decisões e atas.",
    records: [
      { id: 312, title: "Alinhamento operacional semanal", category: "Operação", owner: "Ícaro Simoes", status: "Agendada", updatedAt: today },
      { id: 311, title: "Comitê de segurança", category: "Governança", owner: "Marina Costa", status: "Em andamento", updatedAt: "18/06/2026" },
      { id: 310, title: "Revisão de indicadores", category: "Gestão", owner: "Carlos Reis", status: "Concluído", updatedAt: "17/06/2026" },
    ],
  },
  "relatorios-turno": {
    slug: "relatorios-turno", title: "Relatórios de turno", singular: "relatório", action: "Novo relatório",
    description: "Consolide ocorrências, equipe, manutenção e passagem de turno.",
    records: [
      { id: 821, title: "Turno manhã — Bloco A", category: "Manhã", owner: "Ana Souza", status: "Em andamento", updatedAt: today },
      { id: 820, title: "Turno noite — Bloco B", category: "Noite", owner: "Rafael Lima", status: "Aguardando", updatedAt: "18/06/2026" },
      { id: 819, title: "Turno tarde — Geral", category: "Tarde", owner: "Marina Costa", status: "Concluído", updatedAt: "18/06/2026" },
    ],
  },
  inspecoes: {
    slug: "inspecoes", title: "Inspeções", singular: "inspeção", action: "Nova inspeção",
    description: "Inspeções, vistorias, auditorias e checklists recorrentes.",
    records: [
      { id: 633, title: "Áreas comuns — Torre 1", category: "Predial", owner: "Marina Costa", status: "Em andamento", updatedAt: today },
      { id: 632, title: "Apartamento 302", category: "Vistoria", owner: "Rafael Lima", status: "Aguardando", updatedAt: today },
      { id: 631, title: "Equipamentos de emergência", category: "Segurança", owner: "Ana Souza", status: "Concluído", updatedAt: "17/06/2026" },
    ],
  },
  "diarios-obra": {
    slug: "diarios-obra", title: "Diário de obra", singular: "registro diário", action: "Novo registro",
    description: "Registre atividades, equipes, clima, equipamentos e evidências.",
    records: [
      { id: 177, title: "Reforma do hall principal", category: "Civil", owner: "Rafael Lima", status: "Em andamento", updatedAt: today },
      { id: 176, title: "Adequação elétrica — subsolo", category: "Elétrica", owner: "Carlos Reis", status: "Aguardando", updatedAt: "18/06/2026" },
      { id: 175, title: "Pintura da fachada norte", category: "Acabamento", owner: "Ana Souza", status: "Concluído", updatedAt: "17/06/2026" },
    ],
  },
  manutencao: {
    slug: "manutencao", title: "Manutenção", singular: "ordem", action: "Nova ordem",
    description: "Acompanhe solicitações preventivas e corretivas.",
    records: [
      { id: 490, title: "Revisão da bomba d’água", category: "Preventiva", owner: "Carlos Reis", status: "Agendada", updatedAt: today },
      { id: 489, title: "Iluminação do estacionamento", category: "Corretiva", owner: "Rafael Lima", status: "Em andamento", updatedAt: today },
      { id: 488, title: "Teste do gerador", category: "Preventiva", owner: "Ana Souza", status: "Concluído", updatedAt: "16/06/2026" },
    ],
  },
  "ordens-servico": {
    slug: "ordens-servico", title: "Ordens de Serviço", singular: "ordem de serviço", action: "Nova OS", layout: "kanban",
    description: "Crie, atribua e acompanhe ordens de serviço com workflow completo.",
    records: [],
  },
  procedimentos: {
    slug: "procedimentos", title: "Procedimentos", singular: "procedimento", action: "Novo procedimento",
    description: "Gerencie documentos operacionais, SOPs e manuais da empresa.",
    records: [
      { id: 1, title: "Check-in / Check-out", category: "Recepção", owner: "Administração", status: "Ativo", updatedAt: today },
      { id: 2, title: "Procedimento de governança", category: "Governança", owner: "Administração", status: "Ativo", updatedAt: today },
      { id: 3, title: "Manutenção preventiva", category: "Manutenção", owner: "Administração", status: "Ativo", updatedAt: today },
    ],
  },
  cadastros: {
    slug: "cadastros", title: "Cadastros", singular: "cadastro", action: "Novo cadastro",
    description: "Gerencie setores, locais e funções da empresa.",
    records: [],
  },
  "cadastros/setores": {
    slug: "cadastros/setores", title: "Setores", singular: "setor", action: "Novo setor",
    description: "Departamentos e setores da operação.",
    records: [],
  },
  "cadastros/locais": {
    slug: "cadastros/locais", title: "Locais", singular: "local", action: "Novo local",
    description: "Locais, unidades habitacionais e áreas.",
    records: [],
  },
  "cadastros/funcoes": {
    slug: "cadastros/funcoes", title: "Funções", singular: "função", action: "Nova função",
    description: "Funções e cargos operacionais.",
    records: [],
  },
  "cadastros/procedimentos": {
    slug: "cadastros/procedimentos",
    title: "Procedimentos",
    singular: "procedimento",
    action: "Novo procedimento",
    description: "Gerencie documentos operacionais, SOPs e manuais da empresa.",
    records: [],
  },
  usuarios: {
    slug: "usuarios", title: "Usuários e acesso", singular: "usuário", action: "Convidar usuário",
    description: "Controle pessoas, papéis e permissões da empresa.",
    records: [
      { id: 11, title: "Ícaro Demonstração", category: "Administrador", owner: "icaro@registro.local", status: "Ativo", updatedAt: today },
      { id: 12, title: "Marina Costa", category: "Gestor", owner: "marina@registro.local", status: "Ativo", updatedAt: "18/06/2026" },
      { id: 13, title: "Rafael Lima", category: "Operador", owner: "rafael@registro.local", status: "Pendente", updatedAt: "17/06/2026" },
    ],
  },
  mural: {
    slug: "mural", title: "Mural de avisos", singular: "aviso", action: "Publicar aviso", layout: "cards",
    description: "Comunique mudanças, orientações e informações para a equipe.",
    records: [
      { id: 9, title: "Checklist de fechamento atualizado", category: "Operação", owner: "Marina Costa", status: "Publicado", updatedAt: today, description: "Confira as novas etapas antes de concluir o turno." },
      { id: 8, title: "Inspeções da próxima semana", category: "Governança", owner: "Carlos Reis", status: "Publicado", updatedAt: "18/06/2026", description: "A escala já está disponível para consulta." },
      { id: 7, title: "Manutenção programada", category: "Infraestrutura", owner: "Rafael Lima", status: "Rascunho", updatedAt: "17/06/2026", description: "O gerador será testado na próxima segunda-feira." },
    ],
  },
  configuracoes: {
    slug: "configuracoes", title: "Configurações", singular: "preferência", action: "Salvar alterações", layout: "settings",
    description: "Personalize notificações, idioma e experiência da empresa.", records: [],
  },
  preventivas: {
    slug: "preventivas", title: "Manutenção Preventiva", singular: "plano preventivo", action: "Novo plano",
    description: "Crie planos de manutenção recorrente que geram OS automaticamente.",
    records: [],
  },
  checklists: {
    slug: "checklists", title: "Checklists", singular: "checklist", action: "Novo template",
    description: "Configure templates de verificação recorrente e acompanhe execuções.",
    records: [],
  },
  estoque: {
    slug: "estoque", title: "Estoque", singular: "item", action: "Novo item",
    description: "Controle materiais, produtos de limpeza, amenities e peças de reposição.",
    records: [],
  },
  pendencias: {
    slug: "pendencias", title: "Pendências de Turno", singular: "pendência", action: "Nova pendência",
    description: "Registre pendências para o próximo turno com confirmação de leitura e resolução.",
    records: [],
  },
};

export const navigationModules = [
  "ordens-servico", "reunioes", "relatorios-turno", "inspecoes", "preventivas", "estoque",
];
