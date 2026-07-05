// Package icon gera, em memória, um ícone mínimo para a bandeja do sistema.
// Não há nenhum asset de imagem no repositório: o ícone é um quadrado sólido
// 16x16 desenhado via image/draw + codificado com image/png da stdlib — não
// precisa ser bonito, só existir, já que o valor real está no menu da
// bandeja (abrir configurações / sincronizar / sair).
package icon

import (
	"bytes"
	"encoding/binary"
	"image"
	"image/color"
	"image/png"
)

// PNG retorna os bytes de um PNG 16x16 de cor sólida.
func PNG() []byte {
	const size = 16
	img := image.NewRGBA(image.Rect(0, 0, size, size))
	c := color.RGBA{R: 0x2b, G: 0x6c, B: 0xb0, A: 0xff} // azul sólido, sem significado especial
	for y := 0; y < size; y++ {
		for x := 0; x < size; x++ {
			img.Set(x, y, c)
		}
	}
	var buf bytes.Buffer
	// Encode não deve falhar para uma imagem RGBA in-memory válida; se
	// falhar mesmo assim, retornamos um buffer vazio e deixamos o chamador
	// (tray) tratar isso como "ícone indisponível" sem derrubar o processo.
	if err := png.Encode(&buf, img); err != nil {
		return nil
	}
	return buf.Bytes()
}

// ICO empacota o PNG retornado por PNG() dentro de um contêiner ICO mínimo
// (ICONDIR + ICONDIRENTRY + dados PNG brutos). Esse truque — PNG "cru" dentro
// de um ICO — é suportado nativamente desde o Windows Vista e evita
// implementar um encoder BMP/DIB completo só para um ícone de bandeja.
func ICO() []byte {
	pngData := PNG()
	if len(pngData) == 0 {
		return nil
	}

	var buf bytes.Buffer

	// ICONDIR: reserved(2)=0, type(2)=1 (icon), count(2)=1
	binary.Write(&buf, binary.LittleEndian, uint16(0))
	binary.Write(&buf, binary.LittleEndian, uint16(1))
	binary.Write(&buf, binary.LittleEndian, uint16(1))

	const headerSize = 6
	const entrySize = 16
	offset := uint32(headerSize + entrySize)

	// ICONDIRENTRY
	buf.WriteByte(16)                                             // width (16px; 0 significa 256)
	buf.WriteByte(16)                                             // height
	buf.WriteByte(0)                                              // color count (0 = sem paleta)
	buf.WriteByte(0)                                              // reserved
	binary.Write(&buf, binary.LittleEndian, uint16(1))            // color planes
	binary.Write(&buf, binary.LittleEndian, uint16(32))           // bits per pixel
	binary.Write(&buf, binary.LittleEndian, uint32(len(pngData))) // tamanho dos dados da imagem
	binary.Write(&buf, binary.LittleEndian, offset)               // offset dos dados da imagem

	buf.Write(pngData)
	return buf.Bytes()
}
