# Padrão de documentação do GEOP

Adaptado do padrão Aloji para manter memória e operação junto do código.

| Documento | Responsabilidade |
| --- | --- |
| `README.md` | índice e ponto de entrada |
| `mapa.md` | estado, componentes e domínios |
| `arquitetura.md` | limites e decisões estruturais |
| `domain-model.md` | entidades e invariantes |
| `api-reference.md` | contratos HTTP implementados |
| `web-rotas-ui.md` | rotas, estados e padrões de UI |
| `backlog.md` | prioridade e Definition of Done |
| `memoria-projeto.md` | decisões duráveis e contexto |
| `registro-trabalho.md` | execução cronológica e incidentes |
| `infra/` | deploy, operação, testes e migração |
| `agentes/` | regras Jarvis aplicadas localmente |

Documente contrato atual como atual; futuro deve ser marcado como planejado. Nunca registrar secrets, dados pessoais, IPs privados desnecessários ou credenciais. Mudança técnica e atualização documental pertencem ao mesmo trabalho e, quando houver commit, ao mesmo commit.

## Regra obrigatória

Toda informação pertinente ao desenvolvimento ou ao sistema deve permanecer em `/docs`, e não somente em conversas, mensagens, memória individual ou descrição de commit.

Ao alterar ou descobrir algo, atualize no mínimo:

1. o documento específico do assunto, como API, UI, domínio, segurança ou infraestrutura;
2. `backlog.md`, quando existir trabalho pendente, risco ou dívida técnica;
3. `registro-trabalho.md`, com o registro cronológico da execução;
4. `memoria-projeto.md`, quando houver decisão durável, restrição ou contexto relevante para trabalhos futuros;
5. `mapa.md`, quando mudar o estado de um componente ou domínio.

Revisões técnicas também devem registrar problemas encontrados, evidências de validação e a ordem recomendada de continuação, mesmo que nenhuma correção seja implementada naquele momento.

## Definition of Done documental

Uma mudança só está concluída quando:

- o estado implementado está separado do estado planejado;
- contratos, comandos e caminhos documentados correspondem ao repositório atual;
- riscos, limitações e comportamento demonstrativo estão explícitos;
- testes ou validações executados estão registrados;
- não existem secrets, dumps ou dados sensíveis na documentação versionada.
