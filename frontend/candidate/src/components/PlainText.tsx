


export function PlainText({
  children,
}: {

  children: string;
}) {

  return (
     <div className="plain-text" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
      {children}
    </div>
  );
}
