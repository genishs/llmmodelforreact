interface BoardFile {
  atchFileId: string;
  fileSn: number;
}

interface Props {
  boardFiles?: BoardFile[];
}

function EgovImageGallery({ boardFiles }: Props): JSX.Element {
  const [filesTag, setFilesTag] = React.useState<JSX.Element[]>([]);

  React.useEffect(() => {
    if (!boardFiles) return;

    const ft = boardFiles.map((item, index) =>
      React.createElement(React.Fragment, { key: index },
        React.createElement("img", {
          src: `${SERVER_URL}/image?atchFileId=${item.atchFileId}&fileSn=${item.fileSn}`,
          alt: "",
        }),
        React.createElement("br", null),
      )
    );

    setFilesTag(ft);
  }, [boardFiles]);

  return React.createElement("div", { className: "board_attach_img" }, filesTag);
}

export default EgovImageGallery;