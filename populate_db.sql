-- Populando a tabela usuarios
INSERT INTO usuarios (user_id, nome, created_at) VALUES
(1001, 'Ana Silva', CURRENT_TIMESTAMP),
(1002, 'João Santos', CURRENT_TIMESTAMP),
(1003, 'Maria Oliveira', CURRENT_TIMESTAMP),
(1004, 'Clara Mendes', CURRENT_TIMESTAMP),
(1005, 'Pedro Almeida', CURRENT_TIMESTAMP);

-- Populando a tabela historico
INSERT INTO historico (user_id, conversas, created_at) VALUES
(1001, 'Usuário: Quero agendar um corte de cabelo. Bot: Claro, Ana! Temos horários disponíveis amanhã às 10h ou 14h. Qual prefere?', CURRENT_TIMESTAMP),
(1002, 'Usuário: Qual o preço da manicure? Bot: A manicure custa R$30,00 e leva cerca de 40 minutos.', CURRENT_TIMESTAMP),
(1003, 'Usuário: Vocês fazem progressiva? Bot: Sim, Maria! A escova progressiva custa R$150,00. Deseja agendar?', CURRENT_TIMESTAMP);

-- Populando a tabela servicos
INSERT INTO servicos (servico_id, nome, descricao, preco, duracao_minutos, ativo) VALUES
(1, 'Corte de Cabelo Feminino', 'Corte de cabelo personalizado para mulheres, inclui lavagem e finalização.', 50.00, 45, TRUE),
(2, 'Corte de Cabelo Masculino', 'Corte masculino com tesoura ou máquina, inclui lavagem.', 35.00, 30, TRUE),
(3, 'Coloração', 'Tingimento completo do cabelo com produtos de alta qualidade.', 120.00, 90, TRUE),
(4, 'Manicure', 'Corte, lixamento e esmaltação das unhas das mãos.', 30.00, 40, TRUE),
(5, 'Pedicure', 'Corte, lixamento e esmaltação das unhas dos pés.', 35.00, 45, TRUE),
(6, 'Escova Progressiva', 'Alisamento temporário com produtos sem formol.', 150.00, 120, TRUE),
(7, 'Hidratação Capilar', 'Tratamento intensivo para cabelos ressecados.', 80.00, 60, TRUE),
(8, 'Maquiagem', 'Maquiagem profissional para eventos.', 100.00, 60, TRUE);

-- Populando a tabela agenda
INSERT INTO agenda (user_id, servico_id, dia_semana, horario, data, status) VALUES
(1001, 1, 'segunda', '09:00', '2025-10-20', 'pendente'),
(1001, 4, 'segunda', '10:00', '2025-10-20', 'confirmado'),
(1002, 2, 'terça', '14:00', '2025-10-21', 'pendente'),
(1003, 5, 'quarta', '16:00', '2025-10-22', 'cancelado'),
(1002, 6, 'quinta', '11:00', '2025-10-23', 'pendente'),
(1001, 3, 'sexta', '13:00', '2025-10-24', 'confirmado'),
(1003, 7, 'sabado', '15:00', '2025-10-25', 'pendente'),
(1004, 8, 'domingo', '12:00', '2025-10-26', 'pendente');
