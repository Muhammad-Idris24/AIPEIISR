import "./styles.css";
import AppAuthProvider from "./auth-provider";

export default function Layout({children}:{children:React.ReactNode}) {
  return <html lang="en"><body><AppAuthProvider>{children}</AppAuthProvider></body></html>;
}
